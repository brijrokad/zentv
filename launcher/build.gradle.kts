// AGP 9 compiles Kotlin itself (built-in Kotlin). Pinning the Kotlin Gradle plugin here keeps
// Kotlin at 2.4.21 (>= 2.4.20 fixes CVE-2026-53914, SECURITY_AUDIT.md CY-16).
buildscript {
    dependencies {
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.4.21")
    }
}
plugins {
    id("com.android.application") version "9.5.3" apply false
}
