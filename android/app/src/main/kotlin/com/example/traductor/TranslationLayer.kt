package com.example.traductor

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.Bitmap
import android.graphics.Rect
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.view.View
import kotlin.math.roundToInt

data class TranslatedBlock(val bounds: RectF, val text: String, val background: Int, val centered: Boolean = false,
    val matte: Bitmap? = null, val matteLeft: Int = 0, val matteTop: Int = 0)

/** Fit whole words before allowing the platform to break inside a word. */
private fun fittedTranslationLayout(text: String, paint: TextPaint, rect: RectF, centered: Boolean): StaticLayout {
    val width=rect.width().toInt().coerceAtLeast(12)
    val words=text.split(Regex("\\s+")).filter { it.isNotEmpty() }
    fun layout(size: Float): StaticLayout {
        paint.textSize=size
        return StaticLayout.Builder.obtain(text,0,text.length,paint,width)
            .setAlignment(if(centered)Layout.Alignment.ALIGN_CENTER else Layout.Alignment.ALIGN_NORMAL)
            .setIncludePad(false).setBreakStrategy(Layout.BREAK_STRATEGY_BALANCED)
            .setHyphenationFrequency(Layout.HYPHENATION_FREQUENCY_NONE).build()
    }
    var low=9f;var high=rect.height().coerceAtLeast(low)
    repeat(11) {
        val size=(low+high)/2;val candidate=layout(size)
        if(candidate.height<=rect.height()&&words.all { paint.measureText(it)<=width })low=size else high=size
    }
    return layout(low)
}

/** Compensate the captured pixels so a touch-through overlay erases old glyphs. */
object TranslationMatte {
    fun prepare(block: TranslatedBlock, source: Bitmap, alpha: Float): TranslatedBlock {
        if(alpha<.75f)return block
        val area=Rect(block.bounds.left.toInt()-16,block.bounds.top.toInt()-16,
            kotlin.math.ceil(block.bounds.right.toDouble()).toInt()+16,kotlin.math.ceil(block.bounds.bottom.toDouble()).toInt()+16)
        if(!area.intersect(0,0,source.width,source.height))return block
        val pixels=IntArray(area.width()*area.height())
        source.getPixels(pixels,0,area.width(),area.left,area.top,area.width(),area.height())
        val minimum=intArrayOf(255,255,255);val maximum=intArrayOf(0,0,0)
        for(pixel in pixels)for(channel in 0..2) {
            val value=(pixel shr (16-channel*8)) and 255
            minimum[channel]=minOf(minimum[channel],value);maximum[channel]=maxOf(maximum[channel],value)
        }
        val low=FloatArray(3) { (1-alpha)*maximum[it] }
        val high=FloatArray(3) { alpha*255+(1-alpha)*minimum[it] }
        val background=FloatArray(3) { ((block.background shr (16-it*8)) and 255).toFloat().coerceIn(low[it],high[it]) }
        val inner=RectF(block.bounds).apply { inset(-3f,-2f);offset(-area.left.toFloat(),-area.top.toFloat()) }
        val desired=IntArray(pixels.size)
        for(index in pixels.indices) {
            val x=(index%area.width()).toFloat();val y=(index/area.width()).toFloat()
            val distance=maxOf(inner.left-x,x-inner.right,inner.top-y,y-inner.bottom,0f)
            val strength=(1-distance/12f).coerceIn(0f,1f)
            var color=Color.BLACK
            for(channel in 0..2) {
                val shift=16-channel*8;val original=(pixels[index] shr shift) and 255
                val value=(original*(1-strength)+background[channel]*strength).roundToInt().coerceIn(0,255)
                color=color or (value shl shift)
            }
            desired[index]=color
        }
        val matte=Bitmap.createBitmap(area.width(),area.height(),Bitmap.Config.ARGB_8888)
        matte.setPixels(desired,0,area.width(),0,0,area.width(),area.height())
        if(block.text.isNotEmpty()) {
            val bright=Color.red(block.background)*.299+Color.green(block.background)*.587+Color.blue(block.background)*.114>140
            val ink=(if(bright)low.maxOrNull()!! else high.minOrNull()!!).roundToInt().coerceIn(0,255)
            val paint=TextPaint(Paint.ANTI_ALIAS_FLAG).apply {typeface=Typeface.create("sans-serif-medium",Typeface.NORMAL);color=Color.rgb(ink,ink,ink)}
            val text=fittedTranslationLayout(block.text,paint,inner,block.centered);val canvas=Canvas(matte)
            canvas.save();canvas.clipRect(inner);canvas.translate(inner.left,inner.top+((inner.height()-text.height)/2).coerceAtLeast(0f));text.draw(canvas);canvas.restore()
            matte.getPixels(desired,0,area.width(),0,0,area.width(),area.height())
        }
        for(index in desired.indices) {
            var corrected=Color.BLACK
            for(channel in 0..2) {
                val shift=16-channel*8
                val target=(desired[index] shr shift) and 255;val original=(pixels[index] shr shift) and 255
                val value=((target-(1-alpha)*original)/alpha).roundToInt().coerceIn(0,255)
                corrected=corrected or (value shl shift)
            }
            desired[index]=corrected
        }
        matte.setPixels(desired,0,area.width(),0,0,area.width(),area.height())
        return block.copy(matte=matte,matteLeft=area.left,matteTop=area.top)
    }
    fun release(blocks:List<TranslatedBlock>) {blocks.forEach { if(it.matte?.isRecycled==false)it.matte.recycle() }}
}

/** A single non-touchable overlay avoids stacking touch-obscuring windows. */
class TranslationLayer(context: Context) : View(context) {
    var blocks: List<TranslatedBlock> = emptyList()
        set(value) { field = value; invalidate() }
    private val backgroundPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val textPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        for (block in blocks) {
            if(block.matte!=null&&!block.matte.isRecycled) {canvas.drawBitmap(block.matte,block.matteLeft.toFloat(),block.matteTop.toFloat(),null);continue}
            val rect = RectF(block.bounds)
            rect.inset(-3f, -2f)
            val brightness = Color.red(block.background) * .299 + Color.green(block.background) * .587 + Color.blue(block.background) * .114
            backgroundPaint.color = block.background
            canvas.drawRoundRect(rect, 3f, 3f, backgroundPaint)
            val foreground = if (brightness > 140) Color.rgb(26, 35, 29) else Color.WHITE
            textPaint.color = foreground
            val layout = fittedTranslationLayout(block.text,textPaint,rect,block.centered)
            canvas.save()
            canvas.clipRect(rect)
            canvas.translate(rect.left, rect.top + ((rect.height()-layout.height)/2).coerceAtLeast(0f))
            // A narrow outline keeps the translation legible over the faint
            // original allowed by Android's touch-through opacity limit.
            textPaint.style = Paint.Style.STROKE
            textPaint.strokeWidth = 2.5f
            textPaint.color = block.background
            layout.draw(canvas)
            textPaint.style = Paint.Style.FILL
            textPaint.color = foreground
            layout.draw(canvas)
            canvas.restore()
        }
    }
}
