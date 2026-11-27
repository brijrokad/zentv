// Kotlin + plain Android views. minSdk 30 (the TCL is Android 11), no NDK, no native libraries,
// no coroutines, no AndroidX, no INTERNET (ZENTV_BUILD_PROMPT.md v3, Launcher stack).
plugins {
    id("com.android.application")
}

android {
    namespace = "io.github.brijrokad.zentv"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.brijrokad.zentv"
        minSdk = 30
        targetSdk = 35
        versionCode = 1
        versionName = "0.0.1"
    }

    buildTypes {
        // M3a: the Home-key spike. Its own app ID, so the owner can remove it in Settings > Apps
        // without touching the real launcher (zentv never uninstalls: rule 5). Debug-signed.
        create("spike") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".spike"
            versionNameSuffix = "-spike"
            isDebuggable = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
}
