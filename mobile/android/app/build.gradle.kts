import java.io.File

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "de.eventmonitor.eventmonitor_voice"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    buildFeatures {
        resValues = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "de.eventmonitor.eventmonitor_voice"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("preview") {
            val keystorePath = System.getenv("EVENTMONITOR_ANDROID_PREVIEW_KEYSTORE")
            val keystorePassword = System.getenv("EVENTMONITOR_ANDROID_PREVIEW_STORE_PASSWORD")
            val keyPasswordValue = System.getenv("EVENTMONITOR_ANDROID_PREVIEW_KEY_PASSWORD")
            if (keystorePath != null && keystorePassword != null && keyPasswordValue != null) {
                storeFile = File(keystorePath)
                storePassword = keystorePassword
                keyAlias = "eventmonitor-preview"
                keyPassword = keyPasswordValue
            }
        }
    }

    flavorDimensions += "distribution"
    productFlavors {
        create("preview") {
            dimension = "distribution"
            applicationIdSuffix = ".preview"
            resValue("string", "app_name", "EventMonitor Voice Preview")
            signingConfig = signingConfigs.getByName("preview")
        }
        create("production") {
            dimension = "distribution"
            resValue("string", "app_name", "EventMonitor Voice")
        }
    }

    buildTypes {
        release {
            // Production signing is deliberately not configured in source.
            // The public preview flavor uses a separate key supplied via environment variables.
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
