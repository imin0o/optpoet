"""自動評価指標（P1-045）。AC-03 の判定値ではなく補助指標（evaluation-metrics.md 3.2）。"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from optpoet.errors import StageError
from optpoet.image.grid import GridSpec
from optpoet.render.metrics import (
    METRICS_SPEC_VERSION,
    density,
    density_mae,
    edge_dice,
    evaluate_outputs,
    ssim_score,
)

GRID = GridSpec(columns=4, rows=4)


def gradient(size: int = 32) -> Image.Image:
    values = np.tile(np.linspace(0, 255, size, dtype=np.uint8), (size, 1))
    return Image.fromarray(values, mode="L")


def test_density_direction_is_white_zero_black_one() -> None:
    assert density(Image.new("L", (4, 4), 255)).mean() == pytest.approx(0.0)
    assert density(Image.new("L", (4, 4), 0)).mean() == pytest.approx(1.0)


def test_transparent_pixels_are_composited_over_white() -> None:
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    assert density(image).mean() == pytest.approx(0.0)


def test_identical_images_have_no_error() -> None:
    image = gradient()
    assert density_mae(image, image, GRID) == pytest.approx(0.0, abs=1e-6)
    assert ssim_score(image, image) == pytest.approx(1.0, abs=1e-6)
    assert edge_dice(image, image) == pytest.approx(1.0)


def test_mae_grows_with_difference() -> None:
    target = Image.new("L", (32, 32), 0)
    near = Image.new("L", (32, 32), 64)
    far = Image.new("L", (32, 32), 255)
    assert density_mae(target, near, GRID) < density_mae(target, far, GRID)
    assert density_mae(target, far, GRID) == pytest.approx(1.0, abs=1e-6)


def test_edge_dice_is_one_when_neither_has_edges() -> None:
    flat = Image.new("L", (32, 32), 128)
    assert edge_dice(flat, flat) == 1.0


def test_evaluate_outputs_records_improvement() -> None:
    target = gradient()
    draft = Image.new("L", (32, 32), 255)
    rendered = gradient()
    metrics = evaluate_outputs(target, rendered, GRID, draft=draft)

    assert metrics.spec_version == METRICS_SPEC_VERSION
    assert metrics.mae_draft is not None and metrics.mae_draft > metrics.mae_opt
    assert metrics.improvement_rate == pytest.approx(1.0, abs=1e-6)
    assert "region_mae" not in metrics.to_dict()


def test_improvement_rate_is_undefined_without_draft_error() -> None:
    image = gradient()
    metrics = evaluate_outputs(image, image, GRID, draft=image)
    assert metrics.improvement_rate is None
    assert metrics.to_dict()["mae_draft"] == pytest.approx(0.0, abs=1e-6)


def test_region_mae_limits_cells() -> None:
    target = gradient()
    rendered = Image.new("L", (32, 32), 255)
    region = np.zeros((GRID.rows, GRID.columns), dtype=np.bool_)
    # 最も明るい列だけを見る。白で描いた結果との差はここが最小になる。
    region[:, -1] = True
    metrics = evaluate_outputs(target, rendered, GRID, region=region)
    assert metrics.region_mae is not None
    assert metrics.region_mae < metrics.mae_opt


def test_region_shape_mismatch_is_reported() -> None:
    image = gradient()
    region = np.ones((2, 2), dtype=np.bool_)
    with pytest.raises(StageError) as info:
        evaluate_outputs(image, image, GRID, region=region)
    assert info.value.code == "region_mismatch"


def test_small_image_is_rejected_for_ssim() -> None:
    tiny = Image.new("L", (4, 4), 255)
    with pytest.raises(StageError) as info:
        ssim_score(tiny, tiny)
    assert info.value.code == "image_too_small"
