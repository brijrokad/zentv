// Kotlin + plain Android views. minSdk 30 (the TCL is Android 11), no NDK, no native libraries,
// no coroutines, no AndroidX (ZENTV_BUILD_PROMPT.md v3, Launcher stack; docs/ARCHITECTURE.md §6).
//
// Flavours:
//   core     the default. No uses-permission at all, so no INTERNET.
//   weather  core + INTERNET, used only by WeatherProvider for the Open-Meteo hosts.
import java.util.Properties

plugins {
    id("com.android.application")
}

// Release signing with the owner's own key, kept outside the repo (docs/ARCHITECTURE.md §6, Signing):
// ~/.zentv/keys/release.properties with storeFile (relative to that folder), storePassword, keyAlias,
// keyPassword. Without it, release APKs are built unsigned (as in CI).
val ownerKey = File(System.getProperty("user.home"), ".zentv/keys/release.properties")

android {
    namespace = "io.github.brijrokad.zentv"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.brijrokad.zentv"
        minSdk = 30
        targetSdk = 35
        versionCode = 2
        versionName = "0.1.0"
    }

    flavorDimensions += "net"
    productFlavors {
        create("core") {
            dimension = "net"
            isDefault = true
            buildConfigField("boolean", "WEATHER", "false")
        }
        create("weather") {
            dimension = "net"
            buildConfigField("boolean", "WEATHER", "true")
        }
    }

    signingConfigs {
        if (ownerKey.isFile) {
            create("owner") {
                val p = Properties().apply { ownerKey.inputStream().use { load(it) } }
                storeFile = File(ownerKey.parentFile, p.getProperty("storeFile"))
                storePassword = p.getProperty("storePassword")
                keyAlias = p.getProperty("keyAlias")
                keyPassword = p.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.findByName("owner")
            // R8 drops the unused Kotlin standard library; no reflection, so no keep rules are needed.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }

    buildFeatures {
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    androidResources {
        // The scenes are already JPEG/WebP; storing them uncompressed lets them be read straight from the APK.
        noCompress += listOf("jpg", "webp", "ttf")
    }
    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}

// The owner's private console logos (launcher/local-icons/, git-ignored) are copied into the APK's
// assets/consoles/ at build time. They are other companies' trademarks, so they exist only in builds
// made on the owner's Mac: CI never has the files and always builds the fallback logos.
// Build without them on purpose with: ./gradlew -Pzentv.localIcons=false ...
abstract class CopyLocalIcons : DefaultTask() {
    @get:InputFiles
    @get:PathSensitive(PathSensitivity.NAME_ONLY)
    abstract val icons: ConfigurableFileCollection

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun copy() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        val dir = File(out, "consoles")
        dir.mkdirs()
        icons.files.filter { it.isFile }.forEach { it.copyTo(File(dir, it.name.lowercase()), overwrite = true) }
    }
}

val includeLocalIcons = providers.gradleProperty("zentv.localIcons").map { it != "false" }.getOrElse(true)
val localIcons = rootProject.layout.projectDirectory.dir("local-icons").asFileTree.matching {
    for (name in listOf("playstation", "xbox", "nintendo")) {
        for (ext in listOf("png", "webp", "jpg", "jpeg")) include("$name.$ext")
    }
}

androidComponents {
    onVariants { variant ->
        val task = tasks.register<CopyLocalIcons>(
            "copyLocalIcons" + variant.name.replaceFirstChar { it.uppercase() }
        ) {
            if (includeLocalIcons) icons.from(localIcons)
        }
        variant.sources.assets?.addGeneratedSourceDirectory(task, CopyLocalIcons::outputDir)
    }
}
