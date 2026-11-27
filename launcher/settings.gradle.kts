// zentv launcher. Google and Maven Central only (no JitPack, no plugin portal): SECURITY_AUDIT.md CT-11.
pluginManagement {
    repositories {
        google()
        mavenCentral()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "zentv-launcher"
include(":app")
