package com.np.datamatrixv5

import android.Manifest
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageCapture
import androidx.camera.core.Preview
import androidx.camera.core.SurfaceOrientedMeteringPointFactory
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScanner
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.HybridBinarizer
import java.io.File
import java.util.EnumMap
import java.util.concurrent.TimeUnit
import kotlin.math.max

class MainActivity : ComponentActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var status: TextView
    private lateinit var codeText: TextView
    private lateinit var recipeText: TextView
    private lateinit var ingredientsText: TextView
    private lateinit var shutterButton: Button
    private lateinit var confirmButton: Button
    private lateinit var retryButton: Button
    private lateinit var editRecipeButton: Button
    private lateinit var torchButton: Button

    private var camera: Camera? = null
    private var imageCapture: ImageCapture? = null
    private var pendingCode: String? = null
    private var confirmedCode: String? = null
    private var torchOn = false
    private var busy = false

    private val prefs by lazy { getSharedPreferences("np_datamatrix_v5", MODE_PRIVATE) }

    private val mlScanner by lazy {
        val options = BarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_DATA_MATRIX)
            .build()
        BarcodeScanning.getClient(options)
    }

    private val gmsScanner: GmsBarcodeScanner by lazy {
        val options = GmsBarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_DATA_MATRIX)
            .enableAutoZoom()
            .build()
        GmsBarcodeScanning.getClient(this, options)
    }

    private val cameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else {
            status.text = "Permesso fotocamera negato"
            status.setTextColor(Color.rgb(255, 120, 120))
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            cameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun buildUi() {
        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        }

        previewView = PreviewView(this).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        }
        root.addView(previewView, FrameLayout.LayoutParams(-1, -1))

        val scanOverlay = ScanOverlay(this)
        root.addView(scanOverlay, FrameLayout.LayoutParams(-1, -1))

        val top = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(18), dp(22), dp(16))
            setBackgroundColor(Color.argb(225, 7, 25, 42))
        }
        val title = TextView(this).apply {
            text = "NP • DATAMATRIX V5"
            setTextColor(Color.WHITE)
            textSize = 29f
            setTypeface(typeface, Typeface.BOLD)
        }
        status = TextView(this).apply {
            text = "Inquadra il DataMatrix e premi SCATTA"
            setTextColor(Color.rgb(188, 220, 245))
            textSize = 18f
            setPadding(0, dp(6), 0, 0)
        }
        top.addView(title)
        top.addView(status)
        root.addView(top, FrameLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP))

        val bottom = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(16), dp(20), dp(18))
            setBackgroundColor(Color.argb(238, 8, 25, 43))
        }

        val label = TextView(this).apply {
            text = "CODICE LETTO"
            setTextColor(Color.rgb(154, 205, 247))
            textSize = 15f
            setTypeface(typeface, Typeface.BOLD)
        }
        codeText = TextView(this).apply {
            text = "—"
            setTextColor(Color.WHITE)
            textSize = 31f
            setTypeface(typeface, Typeface.BOLD)
            setPadding(0, dp(4), 0, dp(8))
        }
        recipeText = TextView(this).apply {
            text = "Ricetta: —"
            setTextColor(Color.WHITE)
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            visibility = View.GONE
        }
        ingredientsText = TextView(this).apply {
            text = ""
            setTextColor(Color.rgb(218, 229, 238))
            textSize = 16f
            setPadding(0, dp(6), 0, dp(10))
            maxLines = 7
            visibility = View.GONE
        }

        val actionRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        torchButton = Button(this).apply {
            text = "TORCIA OFF"
            isAllCaps = false
            setOnClickListener { toggleTorch() }
        }
        shutterButton = Button(this).apply {
            text = "●  SCATTA E LEGGI"
            textSize = 18f
            setTypeface(typeface, Typeface.BOLD)
            isAllCaps = false
            setOnClickListener { captureAndRead() }
        }
        actionRow.addView(torchButton, LinearLayout.LayoutParams(0, dp(58), 0.38f).apply { marginEnd = dp(8) })
        actionRow.addView(shutterButton, LinearLayout.LayoutParams(0, dp(58), 0.62f))

        val confirmRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            visibility = View.GONE
            tag = "confirmRow"
        }
        confirmButton = Button(this).apply {
            text = "✓ CONFERMA"
            isAllCaps = false
            setOnClickListener { confirmCode() }
        }
        retryButton = Button(this).apply {
            text = "↻ RIPROVA"
            isAllCaps = false
            setOnClickListener { resetForNextScan() }
        }
        confirmRow.addView(confirmButton, LinearLayout.LayoutParams(0, dp(56), 1f).apply { marginEnd = dp(8) })
        confirmRow.addView(retryButton, LinearLayout.LayoutParams(0, dp(56), 1f))

        editRecipeButton = Button(this).apply {
            text = "RICETTA / INGREDIENTI"
            isAllCaps = false
            visibility = View.GONE
            setOnClickListener {
                val code = confirmedCode ?: pendingCode ?: return@setOnClickListener
                editRecipe(code)
            }
        }

        bottom.addView(label)
        bottom.addView(codeText)
        bottom.addView(recipeText)
        bottom.addView(ingredientsText)
        bottom.addView(actionRow, LinearLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT))
        bottom.addView(confirmRow, LinearLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) })
        bottom.addView(editRecipeButton, LinearLayout.LayoutParams(-1, dp(54)).apply { topMargin = dp(8) })

        root.addView(bottom, FrameLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
        setContentView(root)
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                val provider = future.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }
                imageCapture = ImageCapture.Builder()
                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                    .build()
                provider.unbindAll()
                camera = provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageCapture)
                camera?.cameraControl?.setZoomRatio(1.0f)
                status.text = "Inquadra come nella fotocamera Samsung e premi SCATTA"
            } catch (e: Exception) {
                status.text = "Errore fotocamera: ${e.message ?: "riprova"}"
                status.setTextColor(Color.rgb(255, 120, 120))
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun captureAndRead() {
        if (busy) return
        val capture = imageCapture ?: return
        busy = true
        shutterButton.isEnabled = false
        status.text = "Messa a fuoco…"
        status.setTextColor(Color.rgb(188, 220, 245))

        try {
            val factory = SurfaceOrientedMeteringPointFactory(
                previewView.width.toFloat().coerceAtLeast(1f),
                previewView.height.toFloat().coerceAtLeast(1f)
            )
            val point = factory.createPoint(previewView.width / 2f, previewView.height / 2f)
            val action = FocusMeteringAction.Builder(point, FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE)
                .setAutoCancelDuration(2, TimeUnit.SECONDS)
                .build()
            camera?.cameraControl?.startFocusAndMetering(action)
        } catch (_: Exception) {}

        val file = File(cacheDir, "np_dm_${System.currentTimeMillis()}.jpg")
        val options = ImageCapture.OutputFileOptions.Builder(file).build()

        previewView.postDelayed({
            capture.takePicture(
                options,
                ContextCompat.getMainExecutor(this),
                object : ImageCapture.OnImageSavedCallback {
                    override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                        status.text = "Analizzo lo scatto…"
                        decodeStill(file)
                    }

                    override fun onError(exception: ImageCaptureException) {
                        busy = false
                        shutterButton.isEnabled = true
                        status.text = "Errore scatto: ${exception.message ?: "riprova"}"
                        status.setTextColor(Color.rgb(255, 120, 120))
                    }
                }
            )
        }, 280)
    }

    private fun decodeStill(file: File) {
        val image = try { InputImage.fromFilePath(this, Uri.fromFile(file)) } catch (_: Exception) { null }
        if (image == null) {
            tryFallbackScanner()
            return
        }

        mlScanner.process(image)
            .addOnSuccessListener { barcodes ->
                val value = barcodes.firstOrNull { it.format == Barcode.FORMAT_DATA_MATRIX }
                    ?.rawValue?.trim().orEmpty()
                if (value.isNotBlank()) {
                    showDetected(value, "Scatto HD")
                } else {
                    val zxing = tryZxing(file)
                    if (!zxing.isNullOrBlank()) showDetected(zxing, "Scatto HD / DPM") else tryFallbackScanner()
                }
            }
            .addOnFailureListener {
                val zxing = tryZxing(file)
                if (!zxing.isNullOrBlank()) showDetected(zxing, "Scatto HD / DPM") else tryFallbackScanner()
            }
    }

    private fun tryFallbackScanner() {
        status.text = "Non trovato nello scatto: provo il lettore Google…"
        gmsScanner.startScan()
            .addOnSuccessListener { barcode ->
                val value = barcode.rawValue?.trim().orEmpty().ifBlank { barcode.displayValue?.trim().orEmpty() }
                if (value.isNotBlank()) showDetected(value, "Scanner Google") else noCode()
            }
            .addOnCanceledListener { noCode("Scansione annullata") }
            .addOnFailureListener { noCode("DataMatrix non letto") }
    }

    private fun tryZxing(file: File): String? {
        val bitmap = decodeScaledBitmap(file, 2600) ?: return null
        val variants = mutableListOf<Bitmap>()
        variants.add(bitmap)
        try {
            val cropW = (bitmap.width * 0.72f).toInt().coerceAtLeast(1)
            val cropH = (bitmap.height * 0.72f).toInt().coerceAtLeast(1)
            val x = ((bitmap.width - cropW) / 2).coerceAtLeast(0)
            val y = ((bitmap.height - cropH) / 2).coerceAtLeast(0)
            variants.add(Bitmap.createBitmap(bitmap, x, y, cropW, cropH))
        } catch (_: Exception) {}

        val hints = EnumMap<DecodeHintType, Any>(DecodeHintType::class.java).apply {
            put(DecodeHintType.POSSIBLE_FORMATS, listOf(BarcodeFormat.DATA_MATRIX))
            put(DecodeHintType.TRY_HARDER, true)
            put(DecodeHintType.ALSO_INVERTED, true)
        }

        for (bmp in variants) {
            try {
                val pixels = IntArray(bmp.width * bmp.height)
                bmp.getPixels(pixels, 0, bmp.width, 0, 0, bmp.width, bmp.height)
                val source = RGBLuminanceSource(bmp.width, bmp.height, pixels)
                val binary = BinaryBitmap(HybridBinarizer(source))
                val text = MultiFormatReader().decode(binary, hints).text?.trim()
                if (!text.isNullOrBlank()) return text
            } catch (_: Exception) {}
        }
        return null
    }

    private fun decodeScaledBitmap(file: File, maxSide: Int): Bitmap? {
        return try {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(file.absolutePath, bounds)
            var sample = 1
            val largest = max(bounds.outWidth, bounds.outHeight)
            while (largest / sample > maxSide * 2) sample *= 2
            val opts = BitmapFactory.Options().apply { inSampleSize = sample }
            BitmapFactory.decodeFile(file.absolutePath, opts)
        } catch (_: Exception) { null }
    }

    private fun showDetected(value: String, source: String) {
        busy = false
        shutterButton.isEnabled = true
        pendingCode = value
        confirmedCode = null
        codeText.text = value
        status.text = "DataMatrix letto ($source). Confermi?"
        status.setTextColor(Color.rgb(255, 216, 94))
        recipeText.visibility = View.GONE
        ingredientsText.visibility = View.GONE
        editRecipeButton.visibility = View.GONE
        findConfirmRow()?.visibility = View.VISIBLE
    }

    private fun confirmCode() {
        val code = pendingCode ?: return
        confirmedCode = code
        status.text = "✓ CODICE CONFERMATO"
        status.setTextColor(Color.rgb(74, 255, 140))
        findConfirmRow()?.visibility = View.GONE
        showRecipe(code)
        editRecipeButton.visibility = View.VISIBLE
    }

    private fun showRecipe(code: String) {
        val name = prefs.getString("recipe_name_$code", null)
        val ingredients = prefs.getString("recipe_ing_$code", null)
        recipeText.visibility = View.VISIBLE
        ingredientsText.visibility = View.VISIBLE
        if (name.isNullOrBlank()) {
            recipeText.text = "Ricetta: non ancora associata"
            ingredientsText.text = "Il DataMatrix contiene solo il codice “$code”. Premi RICETTA / INGREDIENTI per associare il nome della ricetta e la composizione: dalle prossime scansioni compariranno automaticamente."
        } else {
            recipeText.text = "Ricetta: $name"
            ingredientsText.text = if (ingredients.isNullOrBlank()) {
                "Ingredienti: non inseriti"
            } else {
                "INGREDIENTI\n$ingredients"
            }
        }
    }

    private fun editRecipe(code: String) {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), 0)
        }
        val name = EditText(this).apply {
            hint = "Nome ricetta"
            setText(prefs.getString("recipe_name_$code", ""))
            singleLine = true
        }
        val ingredients = EditText(this).apply {
            hint = "Ingredienti, uno per riga\nEs. pomodoro 100 kg\nbasilico 5 kg"
            setText(prefs.getString("recipe_ing_$code", ""))
            minLines = 7
            gravity = Gravity.TOP
        }
        box.addView(name, LinearLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT))
        box.addView(ingredients, LinearLayout.LayoutParams(-1, dp(190)).apply { topMargin = dp(8) })

        AlertDialog.Builder(this)
            .setTitle("Scheda codice $code")
            .setView(box)
            .setPositiveButton("SALVA") { _, _ ->
                prefs.edit()
                    .putString("recipe_name_$code", name.text.toString().trim())
                    .putString("recipe_ing_$code", ingredients.text.toString().trim())
                    .apply()
                showRecipe(code)
            }
            .setNegativeButton("ANNULLA", null)
            .show()
    }

    private fun resetForNextScan() {
        pendingCode = null
        confirmedCode = null
        codeText.text = "—"
        recipeText.visibility = View.GONE
        ingredientsText.visibility = View.GONE
        editRecipeButton.visibility = View.GONE
        findConfirmRow()?.visibility = View.GONE
        status.text = "Inquadra il DataMatrix e premi SCATTA"
        status.setTextColor(Color.rgb(188, 220, 245))
    }

    private fun noCode(message: String = "DataMatrix non letto: riprova") {
        busy = false
        shutterButton.isEnabled = true
        status.text = message
        status.setTextColor(Color.rgb(255, 130, 130))
    }

    private fun toggleTorch() {
        torchOn = !torchOn
        camera?.cameraControl?.enableTorch(torchOn)
        torchButton.text = if (torchOn) "TORCIA ON" else "TORCIA OFF"
    }

    private fun findConfirmRow(): View? {
        val root = codeText.parent as? ViewGroup ?: return null
        for (i in 0 until root.childCount) {
            val v = root.getChildAt(i)
            if (v.tag == "confirmRow") return v
        }
        return null
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private class ScanOverlay(context: android.content.Context) : View(context) {
        private val white = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            style = Paint.Style.STROKE
            strokeWidth = 5f
        }
        private val green = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.rgb(50, 255, 135)
            style = Paint.Style.STROKE
            strokeWidth = 4f
        }
        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            val size = width * 0.46f
            val left = (width - size) / 2f
            val top = height * 0.29f
            val rect = RectF(left, top, left + size, top + size)
            canvas.drawRoundRect(rect, 28f, 28f, white)
            val cx = width / 2f
            val cy = top + size / 2f
            canvas.drawLine(cx - 42f, cy, cx + 42f, cy, green)
            canvas.drawLine(cx, cy - 42f, cx, cy + 42f, green)
            canvas.drawCircle(cx, cy, 20f, green)
        }
    }
}
