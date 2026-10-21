package com.np.datamatrixv3

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Build
import android.os.Bundle
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
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
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
import kotlin.math.min

class MainActivity : ComponentActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var statusText: TextView
    private lateinit var codeText: TextView
    private lateinit var zoomText: TextView
    private lateinit var torchButton: Button
    private lateinit var analyzerExecutor: ExecutorService
    private lateinit var scanner: BarcodeScanner

    private var camera: Camera? = null
    private var torchOn = false
    private var zoom = 2.5f
    private var minZoom = 1f
    private var maxZoom = 6f
    private var frameCounter = 0
    private var lastCode = ""
    private var lastReadAt = 0L

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else statusText.text = "Permesso fotocamera negato"
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
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun buildUi() {
        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }

        previewView = PreviewView(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        }
        root.addView(previewView)
        root.addView(GuideView(this), FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ))

        val top = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(10), dp(16), dp(10))
            setBackgroundColor(Color.argb(210, 5, 25, 44))
        }
        top.addView(TextView(this).apply {
            text = "NP  •  DATAMATRIX DPM"
            setTextColor(Color.WHITE)
            textSize = 23f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        })
        statusText = TextView(this).apply {
            text = "Avvio scanner…"
            setTextColor(Color.rgb(176, 220, 255))
            textSize = 16f
            setPadding(0, dp(3), 0, 0)
        }
        top.addView(statusText)
        root.addView(top, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.TOP
        ))

        val bottom = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(10), dp(14), dp(12))
            setBackgroundColor(Color.argb(225, 5, 22, 39))
        }
        bottom.addView(TextView(this).apply {
            text = "CODICE LETTO"
            setTextColor(Color.rgb(174, 213, 248))
            textSize = 14f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        })
        codeText = TextView(this).apply {
            text = "—"
            setTextColor(Color.WHITE)
            textSize = 20f
            setPadding(0, dp(2), 0, dp(7))
            setTextIsSelectable(true)
        }
        bottom.addView(codeText)

        val controls = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        val minus = makeButton("−")
        zoomText = TextView(this).apply {
            text = "ZOOM 2.5×"
            setTextColor(Color.WHITE)
            textSize = 15f
            gravity = Gravity.CENTER
        }
        val plus = makeButton("+")
        torchButton = makeButton("TORCIA OFF")
        val focus = makeButton("FUOCO")
        controls.addView(minus, LinearLayout.LayoutParams(0, dp(50), 1f))
        controls.addView(zoomText, LinearLayout.LayoutParams(0, dp(50), 1.5f))
        controls.addView(plus, LinearLayout.LayoutParams(0, dp(50), 1f))
        controls.addView(torchButton, LinearLayout.LayoutParams(0, dp(50), 1.9f))
        controls.addView(focus, LinearLayout.LayoutParams(0, dp(50), 1.6f))
        bottom.addView(controls)

        bottom.addView(TextView(this).apply {
            text = "Metti IL CENTRO del DataMatrix sulla croce verde. Sul tappo nero prova prima con TORCIA OFF."
            setTextColor(Color.rgb(225, 235, 244))
            textSize = 13f
            setPadding(0, dp(7), 0, 0)
        })

        root.addView(bottom, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM
        ))

        minus.setOnClickListener { setZoom(zoom - 0.5f) }
        plus.setOnClickListener { setZoom(zoom + 0.5f) }
        torchButton.setOnClickListener {
            torchOn = !torchOn
            camera?.cameraControl?.enableTorch(torchOn)
            torchButton.text = if (torchOn) "TORCIA ON" else "TORCIA OFF"
            statusText.text = if (torchOn) "Torcia accesa: evita riflessi sul codice" else "Torcia spenta: modalità consigliata"
        }
        focus.setOnClickListener { focusCenter() }
        previewView.setOnTouchListener { _, event ->
            if (event.action == MotionEvent.ACTION_UP) focusAt(event.x, event.y)
            true
        }

        setContentView(root)
    }

    private fun makeButton(value: String) = Button(this).apply {
        text = value
        textSize = 12f
        isAllCaps = false
        setTextColor(Color.BLACK)
    }

    private fun startCamera() {
        statusText.text = "Apro fotocamera…"
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()

            val preview = Preview.Builder()
                .build()
                .also { it.setSurfaceProvider(previewView.surfaceProvider) }

            val analysis = ImageAnalysis.Builder()
                .setTargetResolution(Size(1920, 1440))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            analysis.setAnalyzer(analyzerExecutor) { proxy -> analyze(proxy) }

            provider.unbindAll()
            camera = provider.bindToLifecycle(
                this,
                CameraSelector.DEFAULT_BACK_CAMERA,
                preview,
                analysis
            )

            val zs = camera?.cameraInfo?.zoomState?.value
            minZoom = zs?.minZoomRatio ?: 1f
            maxZoom = zs?.maxZoomRatio ?: 6f
            setZoom(2.5f)

            val exposure = camera?.cameraInfo?.exposureState
            val range = exposure?.exposureCompensationRange
            if (range != null && range.contains(-2)) {
                camera?.cameraControl?.setExposureCompensationIndex(-2)
            }

            statusText.text = "Cercando DataMatrix DPM… torcia OFF"
            previewView.postDelayed({ focusCenter() }, 700)
        }, ContextCompat.getMainExecutor(this))
    }

    private fun analyze(proxy: ImageProxy) {
        try {
            val gray = extractAndRotateGray(proxy)
            if (gray == null) {
                proxy.close(); return
            }

            val zxing = tryZxing(gray)
            if (!zxing.isNullOrBlank()) {
                runOnUiThread { onRead(zxing, "DPM/ZXing") }
                proxy.close()
                return
            }

            frameCounter++
            val invert = frameCounter % 2 == 0
            val bitmap = centerCropBitmap(gray, 0.58f, invert)
            if (bitmap == null) {
                proxy.close(); return
            }

            val input = InputImage.fromBitmap(bitmap, 0)
            scanner.process(input)
                .addOnSuccessListener { codes ->
                    val value = codes.firstOrNull {
                        it.format == Barcode.FORMAT_DATA_MATRIX && !it.rawValue.isNullOrBlank()
                    }?.rawValue
                    if (!value.isNullOrBlank()) {
                        onRead(value, if (invert) "ML Kit invertito" else "ML Kit")
                    } else {
                        updateSearching()
                    }
                }
                .addOnFailureListener { updateSearching() }
                .addOnCompleteListener {
                    bitmap.recycle()
                    proxy.close()
                }
        } catch (_: Exception) {
            proxy.close()
        }
    }

    private fun tryZxing(gray: GrayImage): String? {
        val fractions = floatArrayOf(0.38f, 0.55f, 0.72f)
        for (fraction in fractions) {
            val crop = centerCrop(gray, fraction) ?: continue
            val stretched = stretch(crop.bytes)

            decode(stretched, crop.width, crop.height)?.let { return it.text }
            decode(invert(stretched), crop.width, crop.height)?.let { return it.text }

            val thresholded = otsu(stretched)
            decode(thresholded, crop.width, crop.height)?.let { return it.text }
            val invThreshold = invert(thresholded)
            decode(invThreshold, crop.width, crop.height)?.let { return it.text }

            val expanded = expandDark(invThreshold, crop.width, crop.height)
            decode(expanded, crop.width, crop.height)?.let { return it.text }
        }
        return null
    }

    private fun decode(bytes: ByteArray, w: Int, h: Int): Result? {
        return try {
            val source = PlanarYUVLuminanceSource(bytes, w, h, 0, 0, w, h, false)
            val hints = EnumMap<DecodeHintType, Any>(DecodeHintType::class.java).apply {
                put(DecodeHintType.TRY_HARDER, true)
            }
            DataMatrixReader().decode(BinaryBitmap(HybridBinarizer(source)), hints)
        } catch (_: Exception) {
            null
        }
    }

    private data class GrayImage(val bytes: ByteArray, val width: Int, val height: Int)

    private fun extractAndRotateGray(proxy: ImageProxy): GrayImage? {
        val plane = proxy.planes.firstOrNull() ?: return null
        val width = proxy.width
        val height = proxy.height
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        val buffer = plane.buffer.duplicate()
        val src = ByteArray(width * height)

        for (y in 0 until height) {
            val base = y * rowStride
            for (x in 0 until width) {
                val idx = base + x * pixelStride
                if (idx < buffer.limit()) src[y * width + x] = buffer.get(idx)
            }
        }

        return when (proxy.imageInfo.rotationDegrees) {
            90 -> {
                val out = ByteArray(src.size)
                val nw = height
                val nh = width
                for (y in 0 until height) for (x in 0 until width) {
                    out[x * nw + (height - 1 - y)] = src[y * width + x]
                }
                GrayImage(out, nw, nh)
            }
            180 -> {
                val out = ByteArray(src.size)
                for (i in src.indices) out[src.lastIndex - i] = src[i]
                GrayImage(out, width, height)
            }
            270 -> {
                val out = ByteArray(src.size)
                val nw = height
                val nh = width
                for (y in 0 until height) for (x in 0 until width) {
                    out[(width - 1 - x) * nw + y] = src[y * width + x]
                }
                GrayImage(out, nw, nh)
            }
            else -> GrayImage(src, width, height)
        }
    }

    private fun centerCrop(gray: GrayImage, fraction: Float): GrayImage? {
        val size = (min(gray.width, gray.height) * fraction).toInt().coerceAtLeast(80)
        if (size > gray.width || size > gray.height) return null
        val left = (gray.width - size) / 2
        val top = (gray.height - size) / 2
        val out = ByteArray(size * size)
        for (y in 0 until size) {
            System.arraycopy(gray.bytes, (top + y) * gray.width + left, out, y * size, size)
        }
        return GrayImage(out, size, size)
    }

    private fun centerCropBitmap(gray: GrayImage, fraction: Float, inverted: Boolean): Bitmap? {
        val crop = centerCrop(gray, fraction) ?: return null
        val pixels = IntArray(crop.bytes.size)
        for (i in crop.bytes.indices) {
            var v = crop.bytes[i].toInt() and 0xFF
            if (inverted) v = 255 - v
            pixels[i] = Color.rgb(v, v, v)
        }
        return Bitmap.createBitmap(pixels, crop.width, crop.height, Bitmap.Config.ARGB_8888)
    }

    private fun stretch(src: ByteArray): ByteArray {
        var lo = 255
        var hi = 0
        for (b in src) {
            val v = b.toInt() and 0xFF
            if (v < lo) lo = v
            if (v > hi) hi = v
        }
        if (hi - lo < 20) return src.copyOf()
        val out = ByteArray(src.size)
        val range = hi - lo
        for (i in src.indices) {
            val v = src[i].toInt() and 0xFF
            out[i] = (((v - lo) * 255 / range).coerceIn(0, 255)).toByte()
        }
        return out
    }

    private fun invert(src: ByteArray): ByteArray {
        val out = ByteArray(src.size)
        for (i in src.indices) out[i] = (255 - (src[i].toInt() and 0xFF)).toByte()
        return out
    }

    private fun otsu(src: ByteArray): ByteArray {
        val hist = IntArray(256)
        for (b in src) hist[b.toInt() and 0xFF]++
        val total = src.size
        var sum = 0.0
        for (i in 0..255) sum += i * hist[i]
        var sumB = 0.0
        var wB = 0
        var maxVar = -1.0
        var threshold = 127
        for (t in 0..255) {
            wB += hist[t]
            if (wB == 0) continue
            val wF = total - wB
            if (wF == 0) break
            sumB += t * hist[t]
            val mB = sumB / wB
            val mF = (sum - sumB) / wF
            val between = wB.toDouble() * wF.toDouble() * (mB - mF) * (mB - mF)
            if (between > maxVar) { maxVar = between; threshold = t }
        }
        val out = ByteArray(src.size)
        for (i in src.indices) {
            out[i] = if ((src[i].toInt() and 0xFF) > threshold) 0xFF.toByte() else 0x00
        }
        return out
    }

    private fun expandDark(src: ByteArray, w: Int, h: Int): ByteArray {
        val out = src.copyOf()
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                var dark = false
                loop@ for (dy in -1..1) for (dx in -1..1) {
                    if ((src[(y + dy) * w + (x + dx)].toInt() and 0xFF) < 128) {
                        dark = true; break@loop
                    }
                }
                out[y * w + x] = if (dark) 0x00 else 0xFF.toByte()
            }
        }
        return out
    }

    private fun onRead(value: String, engine: String) {
        val now = System.currentTimeMillis()
        codeText.text = value
        statusText.text = "✓ DATAMATRIX LETTO  •  $engine"
        statusText.setTextColor(Color.rgb(90, 255, 155))
        if (value != lastCode || now - lastReadAt > 1800) vibrate()
        lastCode = value
        lastReadAt = now
    }

    private fun updateSearching() {
        if (System.currentTimeMillis() - lastReadAt > 1800) {
            statusText.text = "Cercando… centra IL CENTRO del codice sulla croce"
            statusText.setTextColor(Color.rgb(176, 220, 255))
        }
    }

    private fun setZoom(value: Float) {
        zoom = value.coerceIn(minZoom, maxZoom)
        camera?.cameraControl?.setZoomRatio(zoom)
        zoomText.text = "ZOOM %.1f×".format(zoom)
    }

    private fun focusAt(x: Float, y: Float) {
        val point = previewView.meteringPointFactory.createPoint(x, y)
        val action = FocusMeteringAction.Builder(
            point,
            FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE
        ).setAutoCancelDuration(4, TimeUnit.SECONDS).build()
        camera?.cameraControl?.startFocusAndMetering(action)
        statusText.text = "Messa a fuoco…"
    }

    private fun focusCenter() {
        if (previewView.width > 0 && previewView.height > 0) {
            focusAt(previewView.width / 2f, previewView.height / 2f)
        }
    }

    private fun vibrate() {
        val vib = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vib.vibrate(VibrationEffect.createOneShot(100, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION") vib.vibrate(100)
        }
    }

    override fun onDestroy() {
        scanner.close()
        analyzerExecutor.shutdown()
        super.onDestroy()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private class GuideView(context: Context) : View(context) {
        private val border = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            style = Paint.Style.STROKE
            strokeWidth = 4f
        }
        private val cross = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.rgb(65, 255, 145)
            style = Paint.Style.STROKE
            strokeWidth = 4f
        }
        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            val cx = width / 2f
            val cy = height / 2f
            val half = min(width, height) * 0.23f
            canvas.drawRoundRect(cx - half, cy - half, cx + half, cy + half, 24f, 24f, border)
            canvas.drawLine(cx - 45, cy, cx + 45, cy, cross)
            canvas.drawLine(cx, cy - 45, cx, cy + 45, cross)
            canvas.drawCircle(cx, cy, 18f, cross)
        }
    }
}
