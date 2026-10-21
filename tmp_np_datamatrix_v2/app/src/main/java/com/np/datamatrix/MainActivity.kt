package com.np.datamatrix

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Size
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.camera.core.AspectRatio
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.Barcode
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.Result
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.datamatrix.DataMatrixReader
import java.util.EnumMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.math.max
import kotlin.math.min

class MainActivity : ComponentActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var statusText: TextView
    private lateinit var codeText: TextView
    private lateinit var zoomText: TextView
    private lateinit var torchButton: Button

    private var camera: Camera? = null
    private var torchOn = false
    private var currentZoom = 1f
    private var minZoom = 1f
    private var maxZoom = 4f

    private lateinit var scanner: BarcodeScanner
    private lateinit var analyzerExecutor: ExecutorService
    private val mainHandler = Handler(Looper.getMainLooper())

    private var lastCode = ""
    private var lastCodeAt = 0L
    private var lastSearchingUiAt = 0L

    companion object {
        private const val CAMERA_PERMISSION = 401
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        analyzerExecutor = Executors.newSingleThreadExecutor()
        scanner = BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_DATA_MATRIX)
                .build()
        )

        buildUi()

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), CAMERA_PERMISSION)
        }
    }

    private fun buildUi() {
        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
        }

        previewView = PreviewView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        }
        root.addView(previewView)

        val guide = ScannerGuideView(this)
        root.addView(guide, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ))

        val top = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(12))
            setBackgroundColor(Color.argb(190, 5, 24, 45))
        }
        val title = TextView(this).apply {
            text = "NP  •  DATAMATRIX"
            setTextColor(Color.WHITE)
            textSize = 24f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        statusText = TextView(this).apply {
            text = "Avvio fotocamera…"
            setTextColor(Color.rgb(176, 220, 255))
            textSize = 17f
            setPadding(0, dp(4), 0, 0)
        }
        top.addView(title)
        top.addView(statusText)
        root.addView(top, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.TOP
        ))

        val bottom = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(14))
            setBackgroundColor(Color.argb(215, 5, 24, 45))
        }

        val label = TextView(this).apply {
            text = "CODICE LETTO"
            setTextColor(Color.rgb(174, 213, 248))
            textSize = 14f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        codeText = TextView(this).apply {
            text = "—"
            setTextColor(Color.WHITE)
            textSize = 20f
            setPadding(0, dp(3), 0, dp(10))
            setTextIsSelectable(true)
        }

        val controls = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }

        val minus = makeButton("−")
        zoomText = TextView(this).apply {
            text = "ZOOM 1.0×"
            setTextColor(Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
        }
        val plus = makeButton("+")
        torchButton = makeButton("TORCIA")
        val focusButton = makeButton("FUOCO")

        controls.addView(minus, LinearLayout.LayoutParams(0, dp(48), 1f))
        controls.addView(zoomText, LinearLayout.LayoutParams(0, dp(48), 1.5f))
        controls.addView(plus, LinearLayout.LayoutParams(0, dp(48), 1f))
        controls.addView(torchButton, LinearLayout.LayoutParams(0, dp(48), 1.7f))
        controls.addView(focusButton, LinearLayout.LayoutParams(0, dp(48), 1.7f))

        val help = TextView(this).apply {
            text = "Metti il DataMatrix ESATTAMENTE sulla croce. Se è piccolo usa +. Tocca il codice per mettere a fuoco."
            setTextColor(Color.rgb(220, 231, 241))
            textSize = 14f
            setPadding(0, dp(9), 0, 0)
        }

        bottom.addView(label)
        bottom.addView(codeText)
        bottom.addView(controls)
        bottom.addView(help)

        root.addView(bottom, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM
        ))

        minus.setOnClickListener { setZoom(currentZoom - 0.5f) }
        plus.setOnClickListener { setZoom(currentZoom + 0.5f) }
        torchButton.setOnClickListener {
            torchOn = !torchOn
            camera?.cameraControl?.enableTorch(torchOn)
            torchButton.text = if (torchOn) "TORCIA ON" else "TORCIA"
        }
        focusButton.setOnClickListener { focusCenter() }

        previewView.setOnTouchListener { _, event ->
            if (event.action == MotionEvent.ACTION_UP) {
                focusAt(event.x, event.y)
            }
            true
        }

        setContentView(root)
    }

    private fun makeButton(textValue: String): Button = Button(this).apply {
        text = textValue
        textSize = 13f
        isAllCaps = false
        setTextColor(Color.BLACK)
    }

    private fun startCamera() {
        statusText.text = "Apro la fotocamera…"
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()

            val preview = Preview.Builder()
                .setTargetAspectRatio(AspectRatio.RATIO_4_3)
                .build()
                .also { it.setSurfaceProvider(previewView.surfaceProvider) }

            val analysis = ImageAnalysis.Builder()
                .setTargetAspectRatio(AspectRatio.RATIO_4_3)
                .setTargetResolution(Size(1280, 960))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            analysis.setAnalyzer(analyzerExecutor) { imageProxy ->
                analyzeFrame(imageProxy)
            }

            provider.unbindAll()
            camera = provider.bindToLifecycle(
                this,
                CameraSelector.DEFAULT_BACK_CAMERA,
                preview,
                analysis
            )

            val zoomState = camera?.cameraInfo?.zoomState?.value
            minZoom = zoomState?.minZoomRatio ?: 1f
            maxZoom = zoomState?.maxZoomRatio ?: 4f
            currentZoom = min(3.5f, maxZoom)
            setZoom(currentZoom)

            statusText.text = "Cercando DataMatrix…"
            previewView.postDelayed({
                focusCenter()
                scheduleCenterFocus()
            }, 600)
        }, ContextCompat.getMainExecutor(this))
    }

    private fun analyzeFrame(imageProxy: ImageProxy) {
        if (imageProxy.image == null) {
            imageProxy.close()
            return
        }

        // Primo tentativo: ZXing sul canale Y, anche invertito. È utile sui codici chiari stampati su sfondo scuro.
        val zxing = tryZxing(imageProxy)
        if (!zxing.isNullOrBlank()) {
            runOnUiThread { onCodeRead(zxing, "ZXing") }
            imageProxy.close()
            return
        }

        // Secondo tentativo: ML Kit. Per i DataMatrix il codice deve attraversare il centro dell'immagine.
        val mediaImage = imageProxy.image ?: run {
            imageProxy.close()
            return
        }
        val input = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)

        scanner.process(input)
            .addOnSuccessListener { barcodes ->
                val value = barcodes.firstOrNull {
                    it.format == Barcode.FORMAT_DATA_MATRIX && !it.rawValue.isNullOrBlank()
                }?.rawValue
                if (!value.isNullOrBlank()) {
                    onCodeRead(value, "ML Kit")
                } else {
                    updateSearchingUi()
                }
            }
            .addOnFailureListener {
                statusText.text = "Errore lettura: ${it.message ?: "scanner"}"
                statusText.setTextColor(Color.rgb(255, 190, 120))
            }
            .addOnCompleteListener {
                imageProxy.close()
            }
    }

    private fun tryZxing(imageProxy: ImageProxy): String? {
        return try {
            val gray = extractAndRotateGray(imageProxy) ?: return null
            val cropScale = 0.72f
            val cropW = (gray.width * cropScale).toInt().coerceAtLeast(32)
            val cropH = (gray.height * cropScale).toInt().coerceAtLeast(32)
            val left = ((gray.width - cropW) / 2).coerceAtLeast(0)
            val top = ((gray.height - cropH) / 2).coerceAtLeast(0)

            val source = PlanarYUVLuminanceSource(
                gray.bytes,
                gray.width,
                gray.height,
                left,
                top,
                cropW,
                cropH,
                false
            )

            decodeZxingSource(source)?.text ?: decodeZxingSource(source.invert())?.text
        } catch (_: Exception) {
            null
        }
    }

    private fun decodeZxingSource(source: com.google.zxing.LuminanceSource): Result? {
        return try {
            val hints = EnumMap<DecodeHintType, Any>(DecodeHintType::class.java).apply {
                put(DecodeHintType.TRY_HARDER, true)
            }
            DataMatrixReader().decode(BinaryBitmap(HybridBinarizer(source)), hints)
        } catch (_: Exception) {
            null
        }
    }

    private data class GrayImage(val bytes: ByteArray, val width: Int, val height: Int)

    private fun extractAndRotateGray(imageProxy: ImageProxy): GrayImage? {
        val plane = imageProxy.planes.firstOrNull() ?: return null
        val width = imageProxy.width
        val height = imageProxy.height
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        val buffer = plane.buffer
        buffer.rewind()

        val src = ByteArray(width * height)
        for (y in 0 until height) {
            val rowStart = y * rowStride
            val outStart = y * width
            for (x in 0 until width) {
                val index = rowStart + x * pixelStride
                if (index < buffer.limit()) {
                    src[outStart + x] = buffer.get(index)
                }
            }
        }

        return when (imageProxy.imageInfo.rotationDegrees) {
            90 -> {
                val out = ByteArray(src.size)
                val newW = height
                val newH = width
                for (y in 0 until height) {
                    for (x in 0 until width) {
                        val nx = height - 1 - y
                        val ny = x
                        out[ny * newW + nx] = src[y * width + x]
                    }
                }
                GrayImage(out, newW, newH)
            }
            180 -> {
                val out = ByteArray(src.size)
                for (i in src.indices) out[src.lastIndex - i] = src[i]
                GrayImage(out, width, height)
            }
            270 -> {
                val out = ByteArray(src.size)
                val newW = height
                val newH = width
                for (y in 0 until height) {
                    for (x in 0 until width) {
                        val nx = y
                        val ny = width - 1 - x
                        out[ny * newW + nx] = src[y * width + x]
                    }
                }
                GrayImage(out, newW, newH)
            }
            else -> GrayImage(src, width, height)
        }
    }

    private fun onCodeRead(value: String, engine: String) {
        val now = System.currentTimeMillis()
        val isNew = value != lastCode || now - lastCodeAt > 1800
        lastCode = value
        lastCodeAt = now

        codeText.text = value
        statusText.text = "✓ DATAMATRIX LETTO  •  $engine"
        statusText.setTextColor(Color.rgb(85, 255, 155))

        if (isNew) vibrateSuccess()
    }

    private fun updateSearchingUi() {
        val now = System.currentTimeMillis()
        if (now - lastSearchingUiAt < 1200) return
        lastSearchingUiAt = now
        if (now - lastCodeAt > 2000) {
            statusText.text = "Cercando… centra la croce e usa lo zoom"
            statusText.setTextColor(Color.rgb(176, 220, 255))
        }
    }

    private fun setZoom(requested: Float) {
        val ratio = requested.coerceIn(minZoom, maxZoom)
        currentZoom = ratio
        camera?.cameraControl?.setZoomRatio(ratio)
        zoomText.text = "ZOOM %.1f×".format(ratio)
        focusCenter()
    }

    private fun focusAt(x: Float, y: Float) {
        val point = previewView.meteringPointFactory.createPoint(x, y)
        val action = FocusMeteringAction.Builder(
            point,
            FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE
        ).setAutoCancelDuration(2, TimeUnit.SECONDS).build()
        camera?.cameraControl?.startFocusAndMetering(action)
        statusText.text = "Messa a fuoco…"
    }

    private fun focusCenter() {
        if (previewView.width <= 0 || previewView.height <= 0) return
        focusAt(previewView.width / 2f, previewView.height / 2f)
    }

    private fun scheduleCenterFocus() {
        mainHandler.postDelayed(object : Runnable {
            override fun run() {
                if (!isFinishing && !isDestroyed) {
                    if (System.currentTimeMillis() - lastCodeAt > 1600) focusCenter()
                    mainHandler.postDelayed(this, 1800)
                }
            }
        }, 1800)
    }

    private fun vibrateSuccess() {
        val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(90, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(90)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == CAMERA_PERMISSION && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            statusText.text = "Permesso fotocamera necessario"
            statusText.setTextColor(Color.RED)
        }
    }

    override fun onDestroy() {
        scanner.close()
        analyzerExecutor.shutdown()
        mainHandler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private class ScannerGuideView(context: Context) : View(context) {
        private val linePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            style = Paint.Style.STROKE
            strokeWidth = 5f
        }
        private val crossPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.rgb(80, 255, 150)
            style = Paint.Style.STROKE
            strokeWidth = 5f
        }
        private val darkPaint = Paint().apply {
            color = Color.argb(65, 0, 0, 0)
            style = Paint.Style.FILL
        }

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            val cx = width / 2f
            val cy = height / 2f
            val box = min(width, height) * 0.46f
            val rect = android.graphics.RectF(cx - box / 2, cy - box / 2, cx + box / 2, cy + box / 2)
            canvas.drawRoundRect(rect, 30f, 30f, linePaint)

            val arm = box * 0.12f
            canvas.drawLine(cx - arm, cy, cx + arm, cy, crossPaint)
            canvas.drawLine(cx, cy - arm, cx, cy + arm, crossPaint)
            canvas.drawCircle(cx, cy, box * 0.055f, crossPaint)
        }
    }
}
