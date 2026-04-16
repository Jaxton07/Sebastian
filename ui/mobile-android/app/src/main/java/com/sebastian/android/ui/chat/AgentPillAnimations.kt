package com.sebastian.android.ui.chat

import androidx.compose.animation.core.InfiniteTransition
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.DpOffset
import androidx.compose.ui.unit.dp

/**
 * 光团运行轨迹的一个关键帧。t 范围 0f..1f，归一化时间。
 */
data class Keyframe(
    val t: Float,
    val offset: DpOffset,
    val alpha: Float,
)

data class KeyframeValue(
    val offset: DpOffset,
    val alpha: Float,
)

/**
 * 按归一化时间在关键帧之间做 easeInOutQuad 插值。
 * 时间越界时夹到首/尾关键帧。
 */
fun interpolateTrajectory(time: Float, keyframes: List<Keyframe>): KeyframeValue {
    require(keyframes.isNotEmpty()) { "keyframes must not be empty" }
    val first = keyframes.first()
    val last = keyframes.last()
    if (time <= first.t) return KeyframeValue(first.offset, first.alpha)
    if (time >= last.t) return KeyframeValue(last.offset, last.alpha)
    for (i in 0 until keyframes.size - 1) {
        val a = keyframes[i]
        val b = keyframes[i + 1]
        if (time >= a.t && time <= b.t) {
            val raw = (time - a.t) / (b.t - a.t)
            val eased = easeInOutQuad(raw)
            return KeyframeValue(
                offset = DpOffset(
                    x = lerpDp(a.offset.x, b.offset.x, eased),
                    y = lerpDp(a.offset.y, b.offset.y, eased),
                ),
                alpha = lerpFloat(a.alpha, b.alpha, eased),
            )
        }
    }
    return KeyframeValue(last.offset, last.alpha)
}

internal fun easeInOutQuad(t: Float): Float =
    if (t < 0.5f) 2f * t * t
    else 1f - ((-2f * t + 2f).let { it * it }) / 2f

internal fun lerpDp(a: Dp, b: Dp, t: Float): Dp = a + (b - a) * t
internal fun lerpFloat(a: Float, b: Float, t: Float): Float = a + (b - a) * t

// ═══════════════════════════════════════════════════════════════
// OrbsAnimation · THINKING · 4 光团漂移
// ═══════════════════════════════════════════════════════════════

// 4 条独立轨迹，数值等价于 spec 视觉稿 v5 的 CSS keyframes
private val TRAJECTORY_1 = listOf(
    Keyframe(0.00f, DpOffset(0.dp, 0.dp),    alpha = 0.6f),
    Keyframe(0.50f, DpOffset(8.dp, (-4).dp), alpha = 1.0f),
    Keyframe(1.00f, DpOffset(0.dp, 0.dp),    alpha = 0.6f),
)
private val TRAJECTORY_2 = listOf(
    Keyframe(0.00f, DpOffset(0.dp, 0.dp),     alpha = 0.9f),
    Keyframe(0.40f, DpOffset((-4).dp, 5.dp),  alpha = 0.5f),
    Keyframe(0.75f, DpOffset(4.dp, (-3).dp),  alpha = 1.0f),
    Keyframe(1.00f, DpOffset(0.dp, 0.dp),     alpha = 0.9f),
)
private val TRAJECTORY_3 = listOf(
    Keyframe(0.00f, DpOffset(0.dp, 0.dp),        alpha = 0.4f),
    Keyframe(0.50f, DpOffset((-10).dp, (-6).dp), alpha = 1.0f),
    Keyframe(1.00f, DpOffset(0.dp, 0.dp),        alpha = 0.4f),
)
private val TRAJECTORY_4 = listOf(
    Keyframe(0.00f, DpOffset(0.dp, 0.dp),       alpha = 1.0f),
    Keyframe(0.45f, DpOffset((-12).dp, 4.dp),   alpha = 0.5f),
    Keyframe(1.00f, DpOffset(0.dp, 0.dp),       alpha = 1.0f),
)

// 4 颗光团圆心基准（容器 32dp × 22dp；原始 top/left 加半径 3.5dp 得圆心）
private val ORB_BASE_1 = DpOffset(3.5.dp, 11.5.dp)
private val ORB_BASE_2 = DpOffset(13.5.dp, 7.5.dp)
private val ORB_BASE_3 = DpOffset(21.5.dp, 15.5.dp)
private val ORB_BASE_4 = DpOffset(25.5.dp, 9.5.dp)

private const val ORB_RADIUS_DP = 3.5f
private const val ORBS_CONTAINER_W_DP = 32f
private const val ORBS_CONTAINER_H_DP = 22f

@Composable
private fun InfiniteTransition.normalizedTime(periodMs: Int, label: String): State<Float> =
    animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(periodMs, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = label,
    )

/**
 * 4 光团异步漂移 + 各自 alpha 起伏，模拟"思绪打转"。
 * 周期：3.8s / 4.4s / 5.0s / 4.1s（互质，避免同步）。
 */
@Composable
fun OrbsAnimation(
    accent: Color,
    glowAlphaScale: Float = 1f,
    modifier: Modifier = Modifier,
) {
    val t = rememberInfiniteTransition(label = "orbs")
    val p1 by t.normalizedTime(3800, "orb1")
    val p2 by t.normalizedTime(4400, "orb2")
    val p3 by t.normalizedTime(5000, "orb3")
    val p4 by t.normalizedTime(4100, "orb4")

    Canvas(
        modifier
            .size(ORBS_CONTAINER_W_DP.dp, ORBS_CONTAINER_H_DP.dp)
            .graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen },
    ) {
        drawOrb(p1, ORB_BASE_1, TRAJECTORY_1, accent, glowAlphaScale)
        drawOrb(p2, ORB_BASE_2, TRAJECTORY_2, accent, glowAlphaScale)
        drawOrb(p3, ORB_BASE_3, TRAJECTORY_3, accent, glowAlphaScale)
        drawOrb(p4, ORB_BASE_4, TRAJECTORY_4, accent, glowAlphaScale)
    }
}

private fun DrawScope.drawOrb(
    progress: Float,
    basePos: DpOffset,
    trajectory: List<Keyframe>,
    accent: Color,
    glowAlphaScale: Float,
) {
    val v = interpolateTrajectory(progress, trajectory)
    val cx = (basePos.x + v.offset.x).toPx()
    val cy = (basePos.y + v.offset.y).toPx()
    val center = Offset(cx, cy)
    val coreAlpha = v.alpha
    val glowAlpha = v.alpha * glowAlphaScale
    val rPx = ORB_RADIUS_DP.dp.toPx()

    // 外辉
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(accent.copy(alpha = glowAlpha * 0.25f), Color.Transparent),
            center = center,
            radius = rPx * 2.8f,
        ),
        radius = rPx * 2.8f,
        center = center,
        blendMode = BlendMode.Plus,
    )
    // 中辉
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(accent.copy(alpha = glowAlpha * 0.55f), Color.Transparent),
            center = center,
            radius = rPx * 1.6f,
        ),
        radius = rPx * 1.6f,
        center = center,
        blendMode = BlendMode.Plus,
    )
    // 核心
    drawCircle(
        color = accent.copy(alpha = coreAlpha),
        radius = rPx,
        center = center,
        blendMode = BlendMode.Plus,
    )
}
