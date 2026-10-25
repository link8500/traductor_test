package com.example.traductor

import android.app.Activity
import android.Manifest
import android.content.pm.PackageManager
import android.content.Intent
import android.media.projection.MediaProjectionConfig
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var pending: MethodChannel.Result? = null
    private var options: Map<String, Any?> = emptyMap()
    private var notificationAsked = false

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "luma/screen_translator")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "status" -> result.success(ScreenTranslatorService.status())
                    "start" -> {
                        if (pending != null) {
                            result.error("busy", "Ya hay una solicitud de permiso en curso.", null)
                        } else if (ScreenTranslatorService.instance != null) {
                            result.error("running", "Detén la sesión antes de cambiar sus idiomas.", null)
                        } else {
                            options = call.arguments as? Map<String, Any?> ?: emptyMap()
                            pending = result
                            if (!Settings.canDrawOverlays(this)) {
                                startActivityForResult(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                    Uri.parse("package:$packageName")), 4101)
                            } else requestCapture()
                        }
                    }
                    "stop" -> { stopService(Intent(this, ScreenTranslatorService::class.java)); result.success(null) }
                    "translate" -> { ScreenTranslatorService.instance?.capture(); result.success(null) }
                    else -> result.notImplemented()
                }
            }
    }

    private fun requestCapture() {
        if (Build.VERSION.SDK_INT >= 33 && !notificationAsked && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            notificationAsked = true
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 4103)
            return
        }
        try {
            val manager = getSystemService(MediaProjectionManager::class.java)
            val intent = if (Build.VERSION.SDK_INT >= 34)
                manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
            else manager.createScreenCaptureIntent()
            startActivityForResult(intent, 4102)
        } catch (e: Exception) { fail(e.message ?: "No se pudo pedir la captura.") }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        // Denying notifications does not grant capture or prevent the user
        // from stopping through the toolbar and Android's active-app controls.
        if (requestCode == 4103 && pending != null) requestCapture()
    }

    private fun fail(message: String) {
        pending?.error("permission", message, null)
        pending = null
    }

    @Deprecated("The Flutter activity still forwards permission activity results here.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 4101) {
            if (Settings.canDrawOverlays(this)) requestCapture()
            else fail("Activa el permiso de aparecer sobre otras aplicaciones para usar la barra.")
        } else if (requestCode == 4102) {
            if (resultCode != Activity.RESULT_OK || data == null) {
                fail("La captura fue cancelada. No se está compartiendo la pantalla.")
                return
            }
            try {
                val service = Intent(this, ScreenTranslatorService::class.java)
                    .putExtra("projectionData", data)
                    .putExtra("source", options["source"] as? String ?: "en")
                    .putExtra("target", options["target"] as? String ?: "es")
                    .putExtra("provider", options["provider"] as? String ?: "local")
                    .putExtra("opacity", (options["opacity"] as? Number)?.toFloat() ?: .8f)
                startForegroundService(service)
                pending?.success(null)
                pending = null
                moveTaskToBack(true)
            } catch (e: Exception) { fail(e.message ?: "No se pudo iniciar el servicio.") }
        }
    }

    override fun onDestroy() {
        if (pending != null) fail("La solicitud de captura se cerró.")
        super.onDestroy()
    }
}
