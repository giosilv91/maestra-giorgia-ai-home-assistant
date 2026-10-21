package it.newprinces.datamatrix

import android.Manifest
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.text.InputType
import android.util.Size
import android.widget.ArrayAdapter
import android.widget.EditText
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import it.newprinces.datamatrix.databinding.ActivityMainBinding
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private val recipes = linkedMapOf<String, String>()
    private val history = mutableListOf<String>()
    private var lastCode: String = ""
    private var lastAcceptedAt = 0L
    private var lastAcceptedCode = ""

    private val prefs by lazy { getSharedPreferences("np_datamatrix", MODE_PRIVATE) }

    private val cameraPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startCamera()
            else Toast.makeText(this, "Serve il permesso fotocamera", Toast.LENGTH_LONG).show()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        loadData()
        if (recipes.isEmpty()) {
            recipes["Ricetta 1"] = ""
            saveRecipes()
        }
        refreshRecipes()
        refreshHistory()

        binding.addRecipeButton.setOnClickListener { showAddRecipeDialog() }
        binding.deleteRecipeButton.setOnClickListener { deleteSelectedRecipe() }
        binding.assignButton.setOnClickListener { assignLastCode() }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val cameraProvider = providerFuture.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.previewView.surfaceProvider)
            }

            val options = BarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_DATA_MATRIX)
                .build()
            val scanner = BarcodeScanning.getClient(options)

            val analysis = ImageAnalysis.Builder()
                .setTargetResolution(Size(1280, 720))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            analysis.setAnalyzer(cameraExecutor) { imageProxy ->
                val mediaImage = imageProxy.image
                if (mediaImage == null) {
                    imageProxy.close()
                    return@setAnalyzer
                }

                val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
                scanner.process(image)
                    .addOnSuccessListener { barcodes ->
                        val code = barcodes.firstOrNull()?.rawValue?.trim().orEmpty()
                        if (code.isNotEmpty()) handleCode(code)
                    }
                    .addOnCompleteListener { imageProxy.close() }
            }

            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(
                this,
                CameraSelector.DEFAULT_BACK_CAMERA,
                preview,
                analysis
            )
        }, ContextCompat.getMainExecutor(this))
    }

    private fun handleCode(code: String) {
        val now = System.currentTimeMillis()
        if (code == lastAcceptedCode && now - lastAcceptedAt < 2000) return
        lastAcceptedCode = code
        lastAcceptedAt = now
        lastCode = code

        runOnUiThread {
            binding.codeText.text = code
            val selected = selectedRecipe()
            if (selected == null) {
                setStatus("Aggiungi una ricetta", Color.DKGRAY)
                return@runOnUiThread
            }

            val expectedCode = recipes[selected].orEmpty()
            val owner = recipes.entries.firstOrNull { it.value.isNotBlank() && it.value == code }?.key

            when {
                expectedCode.isBlank() -> {
                    setStatus("CODICE LETTO • da associare a $selected", Color.rgb(224, 138, 0))
                    addHistory("NUOVO", selected, code)
                }
                code == expectedCode -> {
                    setStatus("✓ RICETTA CORRETTA\n$selected", Color.rgb(20, 148, 71))
                    addHistory("OK", selected, code)
                }
                owner != null -> {
                    setStatus("✕ CODICE ERRATO\nÈ della ricetta: $owner", Color.rgb(215, 25, 32))
                    addHistory("ERRORE → $owner", selected, code)
                }
                else -> {
                    setStatus("⚠ CODICE SCONOSCIUTO", Color.rgb(224, 138, 0))
                    addHistory("SCONOSCIUTO", selected, code)
                }
            }
        }
    }

    private fun setStatus(text: String, color: Int) {
        binding.statusText.text = text
        binding.statusText.setTextColor(color)
    }

    private fun selectedRecipe(): String? {
        if (binding.recipeSpinner.count == 0) return null
        return binding.recipeSpinner.selectedItem?.toString()
    }

    private fun assignLastCode() {
        val recipe = selectedRecipe()
        if (recipe == null) {
            Toast.makeText(this, "Prima crea una ricetta", Toast.LENGTH_SHORT).show()
            return
        }
        if (lastCode.isBlank()) {
            Toast.makeText(this, "Prima scansiona un DataMatrix", Toast.LENGTH_SHORT).show()
            return
        }

        val alreadyUsed = recipes.entries.firstOrNull { it.value == lastCode && it.key != recipe }
        if (alreadyUsed != null) {
            AlertDialog.Builder(this)
                .setTitle("Codice già usato")
                .setMessage("Questo DataMatrix è già associato a ${alreadyUsed.key}.")
                .setPositiveButton("OK", null)
                .show()
            return
        }

        recipes[recipe] = lastCode
        saveRecipes()
        Toast.makeText(this, "Codice associato a $recipe", Toast.LENGTH_SHORT).show()
        setStatus("✓ CODICE SALVATO\n$recipe", Color.rgb(20, 148, 71))
    }

    private fun showAddRecipeDialog() {
        val input = EditText(this).apply {
            hint = "Es. Pesto alla genovese"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            setPadding(40, 20, 40, 20)
        }
        AlertDialog.Builder(this)
            .setTitle("Nuova ricetta")
            .setView(input)
            .setNegativeButton("Annulla", null)
            .setPositiveButton("Aggiungi") { _, _ ->
                val name = input.text.toString().trim()
                if (name.isBlank()) return@setPositiveButton
                if (recipes.containsKey(name)) {
                    Toast.makeText(this, "Ricetta già presente", Toast.LENGTH_SHORT).show()
                } else {
                    recipes[name] = ""
                    saveRecipes()
                    refreshRecipes(selectName = name)
                }
            }
            .show()
    }

    private fun deleteSelectedRecipe() {
        val recipe = selectedRecipe() ?: return
        AlertDialog.Builder(this)
            .setTitle("Eliminare ricetta?")
            .setMessage("$recipe verrà rimossa con il suo codice DataMatrix.")
            .setNegativeButton("No", null)
            .setPositiveButton("Sì") { _, _ ->
                recipes.remove(recipe)
                if (recipes.isEmpty()) recipes["Ricetta 1"] = ""
                saveRecipes()
                refreshRecipes()
            }
            .show()
    }

    private fun refreshRecipes(selectName: String? = null) {
        val names = recipes.keys.toList()
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, names)
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        binding.recipeSpinner.adapter = adapter
        if (selectName != null) {
            val index = names.indexOf(selectName)
            if (index >= 0) binding.recipeSpinner.setSelection(index)
        }
    }

    private fun addHistory(result: String, expected: String, code: String) {
        val time = SimpleDateFormat("dd/MM HH:mm:ss", Locale.ITALY).format(Date())
        history.add(0, "$time  [$result]  $expected\n$code")
        while (history.size > 25) history.removeLast()
        saveHistory()
        refreshHistory()
    }

    private fun refreshHistory() {
        binding.historyText.text = if (history.isEmpty()) "Nessuna scansione" else history.joinToString("\n\n")
    }

    private fun saveRecipes() {
        val obj = JSONObject()
        recipes.forEach { (name, code) -> obj.put(name, code) }
        prefs.edit().putString("recipes", obj.toString()).apply()
    }

    private fun saveHistory() {
        val arr = JSONArray()
        history.forEach { arr.put(it) }
        prefs.edit().putString("history", arr.toString()).apply()
    }

    private fun loadData() {
        recipes.clear()
        prefs.getString("recipes", null)?.let { raw ->
            runCatching {
                val obj = JSONObject(raw)
                val keys = obj.keys()
                while (keys.hasNext()) {
                    val k = keys.next()
                    recipes[k] = obj.optString(k, "")
                }
            }
        }

        history.clear()
        prefs.getString("history", null)?.let { raw ->
            runCatching {
                val arr = JSONArray(raw)
                for (i in 0 until arr.length()) history.add(arr.getString(i))
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
    }
}
