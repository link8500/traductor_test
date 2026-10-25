package com.example.traductor

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.*
import android.view.View
import android.view.animation.LinearInterpolator

/** An indeterminate indicator follows the real task, never a guessed duration. */
class TranslateActionView(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var angle = 0f
    private var processing = false
    private val animator = ValueAnimator.ofFloat(0f, 360f).apply {
        duration = 900
        repeatCount = ValueAnimator.INFINITE
        interpolator = LinearInterpolator()
        addUpdateListener { angle = it.animatedValue as Float; invalidate() }
    }

    init { isClickable = true; isFocusable = true; contentDescription = "Traducir pantalla" }

    override fun getAccessibilityClassName(): CharSequence = "android.widget.ImageButton"

    fun setWorking(value: Boolean) {
        processing = value
        isEnabled = !value
        contentDescription = if (value) "Traduciendo pantalla" else "Traducir pantalla"
        if (value && ValueAnimator.areAnimatorsEnabled()) animator.start() else { animator.cancel(); angle = 0f }
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        val cx = width / 2f; val cy = height / 2f
        val radius = minOf(width, height) * .45f
        paint.style = Paint.Style.FILL; paint.color = Color.rgb(214, 238, 168)
        canvas.drawCircle(cx, cy, radius, paint)
        if (processing) {
            paint.style = Paint.Style.STROKE; paint.strokeWidth = radius * .11f
            paint.strokeCap = Paint.Cap.ROUND; paint.color = Color.rgb(66, 101, 74)
            canvas.drawArc(cx-radius*.8f, cy-radius*.8f, cx+radius*.8f, cy+radius*.8f, angle-90, 260f, false, paint)
            paint.style = Paint.Style.FILL
        }
        paint.color = Color.rgb(35, 49, 42); paint.typeface = Typeface.create("sans-serif", Typeface.BOLD)
        paint.textAlign = Paint.Align.CENTER; paint.textSize = radius * .82f
        canvas.drawText("A", cx-radius*.24f, cy+radius*.08f, paint)
        paint.textSize = radius * .7f
        canvas.drawText("文", cx+radius*.24f, cy+radius*.46f, paint)
    }

    override fun onDetachedFromWindow() { animator.cancel(); super.onDetachedFromWindow() }
}
