package com.example.traductor

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.content.res.Configuration
import android.graphics.*
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.hardware.input.InputManager
import android.media.ImageReader
import android.media.Image
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.*
import android.util.DisplayMetrics
import android.view.*
import android.widget.*
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.translate.*
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

class ScreenTranslatorService : Service() {
    companion object {
        var instance: ScreenTranslatorService? = null
            private set
        private var lastMessage = "Listo para activar la barra flotante"
        private var lastError: String? = null
        fun status(): Map<String, Any?> = mapOf("running" to (instance != null),
            "original" to (instance?.original ?: false),
            "message" to lastMessage, "error" to lastError)
    }

    private val handler = Handler(Looper.getMainLooper())
    private val executor = Executors.newSingleThreadExecutor()
    private var recognizer: TextRecognizer? = null
    private var translator: Translator? = null
    @Volatile private var localTranslator: LocalMarian? = null
    private var useLocal = false
    private lateinit var windows: WindowManager
    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var layer: TranslationLayer? = null
    private var toolbar: LinearLayout? = null
    private var toolbarParams: WindowManager.LayoutParams? = null
    private var statusText: TextView? = null
    private var translateButton: TranslateActionView? = null
    private val motion = FrameMotionDetector()
    private var watchMotion = false
    private var lastMotionSample = 0L
    private var toolbarDragging = false
    private var screenWidth = 0
    private var screenHeight = 0
    private var density = 0
    private var captureAfterDownload = false
    private var original = false
    private var busy = false
    private var waitingFrame = false
    private var ready = false
    private var downloading = false
    @Volatile private var destroyed = false
    @Volatile private var revision = 0
    private var source = "en"
    private var target = "es"
    private var opacity = .8f
    private var overlayAlpha = .8f
    private val cache = object : LinkedHashMap<String, String>(256, .75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, String>?): Boolean = size > 600
    }
    private val projectionCallback = object : MediaProjection.Callback() {
        override fun onStop() { stopSelf() }
        override fun onCapturedContentResize(width: Int, height: Int) {
            if (width > 0 && height > 0 && (width != screenWidth || height != screenHeight)) resize(width, height)
        }
    }

    override fun onBind(intent: Intent?) = null

    override fun onCreate() {
        super.onCreate()
        windows = getSystemService(WindowManager::class.java)
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel("screen_translation", "Traducción de pantalla", NotificationManager.IMPORTANCE_LOW))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "stop") { stopSelf(); return START_NOT_STICKY }
        if (instance != null || intent == null) return START_NOT_STICKY
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(710, notification("Preparando captura…"), ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
            else startForeground(710, notification("Preparando captura…"))
            instance = this
            source = intent.getStringExtra("source") ?: "en"
            target = intent.getStringExtra("target") ?: "es"
            require(source != target) { "Elige idiomas diferentes." }
            recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            opacity = intent.getFloatExtra("opacity", .8f).coerceIn(.4f, .8f)
            val data = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra("projectionData", Intent::class.java)
                else @Suppress("DEPRECATION") (intent.getParcelableExtra("projectionData") as? Intent)
            requireNotNull(data) { "Falta el permiso de captura de pantalla." }
            val metrics = screenMetrics()
            screenWidth = metrics.widthPixels; screenHeight = metrics.heightPixels; density = metrics.densityDpi
            createOverlays()
            projection = getSystemService(MediaProjectionManager::class.java).getMediaProjection(Activity.RESULT_OK, data)
            projection!!.registerCallback(projectionCallback, handler)
            reader = newReader(screenWidth, screenHeight)
            virtualDisplay = projection!!.createVirtualDisplay("Luma screen translation", screenWidth, screenHeight, density,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader!!.surface, null, handler)
            useLocal = source == "en" && target == "es" && intent.getStringExtra("provider") != "mlkit"
            if (!useLocal) translator = Translation.getClient(TranslatorOptions.Builder().setSourceLanguage(source).setTargetLanguage(target).build())
            downloadModels()
        } catch (e: Exception) {
            lastError = e.message ?: "No se pudo iniciar la superposición."
            lastMessage = lastError!!
            stopSelf()
        }
        // A capture consent token cannot be reused after a process restart.
        return START_NOT_STICKY
    }

    private fun notification(message: String): Notification {
        val stop = PendingIntent.getService(this, 1, Intent(this, javaClass).setAction("stop"), PendingIntent.FLAG_IMMUTABLE)
        val open = PendingIntent.getActivity(this, 2, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, "screen_translation").setSmallIcon(android.R.drawable.ic_menu_view)
            .setContentTitle("Luma · Traductor flotante").setContentText(message)
            .setContentIntent(open).setOngoing(true).addAction(android.R.drawable.ic_menu_close_clear_cancel, "Detener", stop).build()
    }

    private fun screenMetrics(): DisplayMetrics {
        if (Build.VERSION.SDK_INT >= 30) {
            val bounds = windows.maximumWindowMetrics.bounds
            return DisplayMetrics().apply { widthPixels = bounds.width(); heightPixels = bounds.height(); densityDpi = resources.configuration.densityDpi }
        }
        return DisplayMetrics().also { @Suppress("DEPRECATION") windows.defaultDisplay.getRealMetrics(it) }
    }

    private fun newReader(width: Int, height: Int): ImageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 3).also {
        it.setOnImageAvailableListener({ r ->
            if (!waitingFrame) runCatching {
                r.acquireLatestImage()?.use { frame ->
                    val now = SystemClock.uptimeMillis()
                    if (watchMotion && !toolbarDragging && now - lastMotionSample >= 150) {
                        lastMotionSample = now
                        if (motion.moved(motionSample(frame))) dismissTranslation()
                    }
                }
            }
        }, handler)
    }

    private fun motionSample(frame: Image): IntArray {
        val plane = frame.planes[0]
        val buffer = plane.buffer
        val toolbarLocation = IntArray(2)
        toolbar?.getLocationOnScreen(toolbarLocation)
        val shadow = dp(12)
        val bar = Rect(toolbarLocation[0]-shadow, toolbarLocation[1]-shadow,
            toolbarLocation[0]+(toolbar?.width ?: 0)+shadow, toolbarLocation[1]+(toolbar?.height ?: 0)+shadow)
        val excluded = layer?.blocks?.map { block ->
            // The feathered matte extends beyond the OCR box. Its changing
            // pixels belong to us, not to movement of the underlying page.
            block.matte?.let { matte -> RectF(block.matteLeft.toFloat(),block.matteTop.toFloat(),
                (block.matteLeft+matte.width).toFloat(),(block.matteTop+matte.height).toFloat()) }
                ?.apply { inset(-2f,-2f) } ?: RectF(block.bounds).apply { inset(-5f,-4f) }
        } ?: emptyList()
        return IntArray(64 * 96) { i ->
            val x = ((i % 64 + .5f) * frame.width / 64).toInt().coerceAtMost(frame.width-1)
            val y = ((i / 64 + .5f) * frame.height / 96).toInt().coerceAtMost(frame.height-1)
            val offset = y * plane.rowStride + x * plane.pixelStride
            if (y < frame.height*.06f || y > frame.height*.96f || bar.contains(x,y) ||
                excluded.any { it.contains(x.toFloat(),y.toFloat()) } || offset+2 >= buffer.limit()) -1
            else ((buffer.get(offset).toInt() and 255)*77 + (buffer.get(offset+1).toInt() and 255)*150 +
                (buffer.get(offset+2).toInt() and 255)*29) shr 8
        }
    }

    private fun dismissTranslation() {
        if (!busy && !captureAfterDownload && layer?.blocks.isNullOrEmpty()) return
        revision++; watchMotion = false; motion.reset(); captureAfterDownload = false
        localTranslator?.cancel()
        if (waitingFrame) { waitingFrame = false; busy = false }
        layer?.blocks = emptyList(); layer?.visibility = View.INVISIBLE
        original = true
        toolbar?.visibility = View.VISIBLE
        translateButton?.setWorking(false)
        translateButton?.isEnabled = !busy
        showStatus("Pantalla cambiada · Toca el icono para traducir")
    }

    private fun resize(width: Int, height: Int) {
        if (destroyed || virtualDisplay == null) return
        screenWidth = width; screenHeight = height
        dismissTranslation()
        revision++
        val old = reader
        reader = newReader(width, height)
        virtualDisplay?.resize(width, height, density)
        virtualDisplay?.surface = reader!!.surface
        old?.close()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        val metrics = screenMetrics()
        if (metrics.widthPixels != screenWidth || metrics.heightPixels != screenHeight) resize(metrics.widthPixels, metrics.heightPixels)
        toolbarParams?.let { p -> p.x = p.x.coerceIn(0, (screenWidth-dp(310)).coerceAtLeast(0)); p.y = p.y.coerceIn(0, (screenHeight-dp(64)).coerceAtLeast(0)); toolbar?.let { windows.updateViewLayout(it, p) } }
    }

    private fun downloadModels() {
        if (downloading || destroyed) return
        downloading = true
        if (useLocal) {
            showStatus("Preparando modelo local…")
            executor.execute {
                try {
                    val model = LocalMarian(this)
                    if (destroyed) { model.close(); return@execute }
                    localTranslator = model
                    handler.post {
                        if (!destroyed) {
                            downloading = false; ready = true
                            showStatus("Modelo local listo · Toca el icono")
                            if (captureAfterDownload) { captureAfterDownload = false; capture() }
                        }
                    }
                } catch (error: Throwable) {
                    handler.post { downloading = false; fail("No se pudo preparar el modelo local: ${error.message}") }
                }
            }
            return
        }
        showStatus("Descargando modelos de idioma…")
        translator?.downloadModelIfNeeded(DownloadConditions.Builder().build())
            ?.addOnSuccessListener {
                if (destroyed) return@addOnSuccessListener
                downloading = false; ready = true
                showStatus("Toca el icono para traducir")
                if (captureAfterDownload) { captureAfterDownload = false; capture() }
            }?.addOnFailureListener {
                downloading = false
                fail("No se pudo descargar el modelo. Revisa Internet y toca Traducir para reintentar.")
            }
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).roundToInt()
    private fun contentBounds(): Rect {
        if (Build.VERSION.SDK_INT >= 30) {
            val inset=windows.maximumWindowMetrics.windowInsets.getInsets(
                WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
            return Rect(inset.left,inset.top,screenWidth-inset.right,screenHeight-inset.bottom)
        }
        @Suppress("DEPRECATION") val inset=toolbar?.rootWindowInsets
        @Suppress("DEPRECATION") return Rect(inset?.systemWindowInsetLeft ?: 0,inset?.systemWindowInsetTop ?: dp(24),
            screenWidth-(inset?.systemWindowInsetRight ?: 0),screenHeight-(inset?.systemWindowInsetBottom ?: dp(24)))
    }
    private fun placeToolbar(text: List<Rect>, content: Rect) {
        if(toolbarDragging)return
        val bar=toolbar ?: return;val params=toolbarParams ?: return
        val position=IntArray(2);bar.getLocationOnScreen(position)
        val current=ScreenRect(position[0],position[1],position[0]+bar.width,position[1]+bar.height)
        val safe=toolbarPosition(current,ScreenRect(content.left,content.top,content.right,content.bottom),
            text.map { ScreenRect(it.left,it.top,it.right,it.bottom) },dp(8)) ?: return
        if(safe==current)return
        params.x+=safe.left-current.left;params.y+=safe.top-current.top
        windows.updateViewLayout(bar,params)
        motion.reset();lastMotionSample=SystemClock.uptimeMillis()+200
    }
    private fun background(color: Int, radius: Float) = android.graphics.drawable.GradientDrawable().apply { setColor(color); cornerRadius = radius }

    private fun createOverlays() {
        layer = TranslationLayer(this)
        val flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
        val layerParams = WindowManager.LayoutParams(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, flags, PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.LEFT
            if (Build.VERSION.SDK_INT >= 30) setFitInsetsTypes(0)
            alpha = if (Build.VERSION.SDK_INT >= 31) minOf(opacity, getSystemService(InputManager::class.java).maximumObscuringOpacityForTouch) else opacity
            if (Build.VERSION.SDK_INT >= 28) layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }
        windows.addView(layer, layerParams)
        overlayAlpha=layerParams.alpha
        toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = background(Color.rgb(35, 49, 42), dp(13).toFloat())
            setPadding(dp(8), dp(5), dp(8), dp(5))
            elevation = dp(8).toFloat()
        }
        val row = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        val grip = button("⠿ Luma") {}
        row.addView(grip)
        translateButton = TranslateActionView(this).apply { setOnClickListener { capture() } }
            .also { row.addView(it, LinearLayout.LayoutParams(dp(48), dp(48))) }
        row.addView(button("×") { stopSelf() }.apply { contentDescription = "Cerrar barra" })
        toolbar!!.addView(row)
        statusText = TextView(this).apply { textSize = 9f; setTextColor(Color.rgb(187, 205, 182)); setPadding(dp(5), 0, dp(5), dp(2)); maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END; maxWidth = dp(175) }
        toolbar!!.addView(statusText)
        toolbarParams = WindowManager.LayoutParams(WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
            PixelFormat.TRANSLUCENT).apply { gravity = Gravity.TOP or Gravity.LEFT; x = dp(8); y = dp(90) }
        var downX = 0f; var downY = 0f; var startX = 0; var startY = 0
        grip.setOnTouchListener { _, event ->
            val params = toolbarParams!!
            when (event.action) {
                MotionEvent.ACTION_DOWN -> { toolbarDragging = true; downX = event.rawX; downY = event.rawY; startX = params.x; startY = params.y; true }
                MotionEvent.ACTION_MOVE -> {
                    params.x = (startX + event.rawX-downX).roundToInt().coerceIn(0, (screenWidth-(toolbar?.width ?: 0)).coerceAtLeast(0))
                    params.y = (startY + event.rawY-downY).roundToInt().coerceIn(0, (screenHeight-(toolbar?.height ?: 0)).coerceAtLeast(0))
                    windows.updateViewLayout(toolbar, params); true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> { toolbarDragging = false; motion.reset(); true }
                else -> false
            }
        }
        windows.addView(toolbar, toolbarParams)
    }

    private fun button(label: String, action: () -> Unit) = Button(this).apply {
        text = label; textSize = 12f; isAllCaps = false; gravity = Gravity.CENTER; setTextColor(Color.rgb(214, 238, 168))
        minWidth = 0; minimumWidth = 0; minHeight = 0; minimumHeight = dp(44)
        background = background(Color.TRANSPARENT, 0f)
        setPadding(dp(8), dp(8), dp(8), dp(8)); setOnClickListener { action() }
        contentDescription = label
    }

    private fun showStatus(message: String) {
        if (destroyed) return
        lastError = null; lastMessage = message; statusText?.text = message
        getSystemService(NotificationManager::class.java).notify(710, notification(message))
    }

    private fun fail(message: String) {
        if (destroyed) return
        busy = false; waitingFrame = false; captureAfterDownload = false
        watchMotion = false; motion.reset(); translateButton?.setWorking(false)
        layer?.blocks = emptyList(); layer?.visibility = View.INVISIBLE
        toolbar?.visibility = View.VISIBLE
        showStatus(message); lastError = message
    }

    fun capture() {
        if (destroyed || busy) return
        if (!ready) { captureAfterDownload = true; translateButton?.setWorking(true); downloadModels(); return }
        original = false
        translateButton?.setWorking(true)
        busy = true; waitingFrame = true
        val ticket = ++revision
        watchMotion = false; motion.reset(); layer?.blocks = emptyList()
        // Clear both of our windows from the captured frame. Restore the
        // working icon as soon as that frame is acquired, before running OCR.
        runCatching { reader?.acquireLatestImage()?.close() }
        layer?.visibility = View.INVISIBLE
        toolbar?.visibility = View.INVISIBLE
        handler.postDelayed({ readFrame(ticket, 0) }, 180)
    }

    private fun readFrame(ticket: Int, attempt: Int) {
        if (destroyed || ticket != revision) return
        val image = runCatching { reader?.acquireLatestImage() }.getOrNull()
        if (image == null) {
            if (attempt < 8) handler.postDelayed({ readFrame(ticket, attempt + 1) }, 100)
            else fail("No llegó una imagen. La aplicación puede bloquear la captura.")
            return
        }
        waitingFrame = false
        motion.reference(motionSample(image)); watchMotion = true; lastMotionSample = SystemClock.uptimeMillis()
        toolbar?.visibility = View.VISIBLE
        showStatus("Leyendo y traduciendo pantalla…")
        val content=contentBounds()
        executor.execute {
            var bitmap: Bitmap? = null
            val output = ArrayList<TranslatedBlock>()
            var unchanged = 0
            try {
                val plane = image.planes[0]
                val paddedWidth = image.width + (plane.rowStride - plane.pixelStride * image.width) / plane.pixelStride
                val padded = Bitmap.createBitmap(paddedWidth, image.height, Bitmap.Config.ARGB_8888)
                padded.copyPixelsFromBuffer(plane.buffer)
                bitmap = Bitmap.createBitmap(padded, 0, 0, image.width, image.height)
                if (bitmap !== padded) padded.recycle()
                image.close()
                val recognized = ComicOcr.recognize(recognizer!!, bitmap, localTranslator) { destroyed || ticket != revision }
                val textBounds=recognized.map { Rect(it.bounds) }
                for ((bounds, rawText, centered) in recognized.take(100)) {
                    if (destroyed || ticket != revision || Thread.currentThread().isInterrupted) break
                    if (!fullyVisibleText(ScreenRect(bounds.left,bounds.top,bounds.right,bounds.bottom),
                            ScreenRect(content.left,content.top,content.right,content.bottom),dp(1))) continue
                    val text = normalizeScreenText(rawText)
                    if (text.length < 2 || text.none { it.isLetter() }) continue
                    if (Regex("^\\d[\\d\\s:.,/\\-]*(?:[AaPp][Mm])?$").matches(text)) continue
                    val translated = cache[text] ?: (if (useLocal) localTranslator!!.translate(text)
                        else Tasks.await(translator!!.translate(text), 15, TimeUnit.SECONDS)).also { cache[text] = it }
                    if (translated.equals(text, true)) { unchanged++;continue }
                    val bg = sampleBackground(bitmap, bounds)
                    val styled = if (rawText.filter { it.isLetter() }.all { it.isUpperCase() }) translated.uppercase() else translated
                    output.add(TranslationMatte.prepare(TranslatedBlock(RectF(bounds), styled, bg, centered),bitmap,overlayAlpha))
                }
                handler.post {
                    if (!destroyed) {
                        busy = false
                        translateButton?.setWorking(false)
                        if (ticket != revision) { TranslationMatte.release(output);return@post }
                        placeToolbar(textBounds,content)
                        layer?.blocks = output
                        watchMotion = output.isNotEmpty()
                        layer?.visibility = if (original) View.INVISIBLE else View.VISIBLE
                        showStatus(if (output.isEmpty()) {
                            if(unchanged>0) "Texto conservado · Toca el icono para reintentar" else "Sin texto · Toca el icono para reintentar"
                        } else "${output.size} textos${if(unchanged>0) " · $unchanged conservados" else ""} · Desliza para ver el original")
                    } else TranslationMatte.release(output)
                }
            } catch (e: Exception) {
                TranslationMatte.release(output)
                runCatching { image.close() }
                handler.post {
                    if (ticket == revision) fail("No se pudo traducir: ${e.cause?.message ?: e.message ?: "inténtalo otra vez"}")
                    else if (!destroyed) { busy = false; translateButton?.setWorking(false) }
                }
            } finally { bitmap?.recycle() }
        }
    }

    private fun sampleBackground(bitmap: Bitmap, rect: Rect): Int {
        val samples = listOf(rect.left-3 to rect.top-3, rect.right+3 to rect.top-3, rect.left-3 to rect.bottom+3, rect.right+3 to rect.bottom+3)
            .map { (x,y) -> bitmap.getPixel(x.coerceIn(0, bitmap.width-1), y.coerceIn(0, bitmap.height-1)) }
        // Median corners are less affected by text or a single nearby border.
        val fallback=Color.rgb(samples.map { Color.red(it) }.sorted()[2], samples.map { Color.green(it) }.sorted()[2], samples.map { Color.blue(it) }.sorted()[2])
        return OverlayBackground.dominant(bitmap.width,bitmap.height,rect.left,rect.top,rect.right,rect.bottom) { x,y -> bitmap.getPixel(x,y) } ?: fallback
    }

    override fun onDestroy() {
        destroyed = true
        layer?.blocks=emptyList()
        handler.removeCallbacksAndMessages(null)
        // Let an in-flight ML task release its bitmap before closing clients.
        localTranslator?.cancel()
        executor.execute { localTranslator?.close(); translator?.close(); recognizer?.close() }
        executor.shutdown()
        projection?.unregisterCallback(projectionCallback)
        virtualDisplay?.release(); virtualDisplay = null
        reader?.close(); reader = null
        projection?.stop(); projection = null
        toolbar?.let { runCatching { windows.removeView(it) } }
        layer?.let { runCatching { windows.removeView(it) } }
        instance = null
        if (lastError == null) lastMessage = "Captura detenida · Barra cerrada"
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
}
