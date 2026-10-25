import groovy.json.JsonSlurper
import java.security.MessageDigest
import java.io.File

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.traductor"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        testInstrumentationRunner = "com.example.traductor.QualityBenchmarkRunner"
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.example.traductor"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = maxOf(flutter.minSdkVersion, 26)
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // Keep native dependencies aligned with Flutter's selected targets.
        // Otherwise an emulator-only build advertises ARM libraries without
        // the matching Flutter engine and wastes the emulator's storage.
        val requestedPlatforms = providers.gradleProperty("target-platform").orNull
        if (requestedPlatforms != null && providers.gradleProperty("split-per-abi").orNull != "true") {
            val platformAbis = mapOf("android-arm" to "armeabi-v7a", "android-arm64" to "arm64-v8a", "android-x64" to "x86_64")
            ndk {
                abiFilters.clear()
                abiFilters.addAll(requestedPlatforms.split(",").map { platform ->
                    requireNotNull(platformAbis[platform]) { "Unsupported Flutter platform: $platform" }
                })
            }
        }
        externalNativeBuild {
            cmake { arguments += "-DANDROID_STL=c++_shared" }
        }
    }

    externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt") } }

    buildTypes {
        release {
            if (providers.gradleProperty("lumaBenchmark").orNull == "true") {
                // A separate instrumentation APK needs stable Kotlin/ML Kit
                // names. Release UI smoke tests still use the optimized APK.
                isMinifyEnabled = false
                isShrinkResources = false
                // Keep Flutter's actual release assets; instrumentation can
                // import only its fixtures through UiAutomation's shell pipe.
                isDebuggable = false
            }
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    testBuildType = providers.gradleProperty("lumaTestBuildType").getOrElse("debug")
    sourceSets.getByName("androidTest").assets.srcDir("../../benchmarks/bilingual-comics")
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.mlkit:translate:17.0.3")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.23.2")
}

val verifyLocalModels by tasks.registering {
    val directory=file("../../assets/models/opus-en-es")
    inputs.dir(directory)
    doLast {
        val manifest=JsonSlurper().parse(file("../../assets/models/opus-en-es/manifest.json")) as Map<*,*>
        val hashes=manifest["files"] as Map<*,*>
        for ((entry,expected) in hashes) {
            val name=entry.toString()
            check(File(name).name==name) { "Invalid model asset name" }
            val digest=MessageDigest.getInstance("SHA-256")
            File(directory,name).inputStream().use { input ->
                val buffer=ByteArray(1024*1024)
                while(true) {val count=input.read(buffer);if(count<0)break;digest.update(buffer,0,count)}
            }
            val actual=digest.digest().joinToString("") { "%02x".format(it) }
            check(actual==expected) { "Model checksum mismatch: $name. For an intentional glossary change run tools/check_model_assets.py --refresh." }
        }
    }
}
tasks.named("preBuild").configure { dependsOn(verifyLocalModels) }
