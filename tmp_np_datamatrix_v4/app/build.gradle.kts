plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.np.datamatrix.v4"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.np.datamatrix.v4"
        minSdk = 26
        targetSdk = 35
        versionCode = 4
        versionName = "4.0"
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
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
}
