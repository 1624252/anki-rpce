plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.rpce.speedrun"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.rpce.speedrun"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1"
        // MVP targets arm64; add other ABIs once their .so are built.
        ndk { abiFilters += listOf("arm64-v8a") }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
