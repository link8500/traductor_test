# ML Kit discovers these registrars by manifest class name and calls their
# no-argument constructors reflectively. R8 full mode must keep those members.
-keep class com.google.mlkit.** implements com.google.firebase.components.ComponentRegistrar { *; }

# The separate regression-test APK calls the same production OCR helpers.
-keep class com.example.traductor.ComicText { *; }
-keep class com.example.traductor.ComicRegion { *; }
-keep class com.example.traductor.ComicOcr { *; }
-keep class com.example.traductor.LocalLineRead { *; }
-keep interface kotlin.jvm.functions.Function0 { *; }
-keep class com.example.traductor.FrameMotionDetectorKt { *; }
-keep class com.google.mlkit.vision.text.** { *; }
-keep class com.google.mlkit.vision.common.InputImage { *; }
-keep class com.google.android.gms.tasks.** { *; }
-keep class com.example.traductor.LocalMarian { *; }
