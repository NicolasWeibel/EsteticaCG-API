# Cloudinary Direct Upload - Guía Frontend

## Visión General

El nuevo flujo de upload elimina el envío de archivos a través de Django/Cloud Run. En su lugar:

1. **Frontend obtiene una firma temporal** de Django
2. **Frontend sube archivos directamente** a Cloudinary
3. **Frontend envía solo referencias JSON** a Django

Este cambio resuelve el error `413 Content Too Large` para archivos grandes (especialmente videos) y mejora significativamente el rendimiento.

---

## Flujo Paso a Paso

### 1. Obtener Firma de Upload

**Endpoint:** `POST /api/v1/catalog/upload/sign/`

**Autenticación:** Requiere token de admin

**Request:**

```json
{
  "context": "catalog_treatment_media",
  "resource_type": "video",
  "filename": "mi-video.mp4"
}
```

**Parámetros:**

- `context` _(requerido)_: Contexto de upload (ver tabla de contextos disponibles)
- `resource_type` _(opcional)_: `"image"`, `"video"`, o `"auto"` (default: `"auto"`)
- `filename` _(opcional)_: Nombre del archivo original (solo para referencia)

**Response:**

```json
{
  "signature": "abc123def456...",
  "timestamp": 1234567890,
  "cloud_name": "your-cloud-name",
  "api_key": "123456789",
  "public_id": "catalog/treatments/550e8400-e29b-41d4-a716-446655440000",
  "folder": "catalog/treatments",
  "resource_type": "video",
  "allowed_formats": ["mp4", "mov", "avi", "webm"],
  "max_file_size": 524288000,
  "upload_url": "https://api.cloudinary.com/v1_1/your-cloud/upload"
}
```

---

### 2. Upload Directo a Cloudinary

Usa el `upload_url` y los parámetros de la respuesta anterior para subir el archivo directamente a Cloudinary.

**Ejemplo con JavaScript:**

```javascript
const uploadToCloudinary = async (file, signatureData) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("signature", signatureData.signature);
  formData.append("timestamp", signatureData.timestamp);
  formData.append("api_key", signatureData.api_key);
  formData.append("public_id", signatureData.public_id);
  formData.append("folder", signatureData.folder);

  const response = await fetch(signatureData.upload_url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return await response.json();
  // Returns: { public_id, resource_type, secure_url, width, height, format, ... }
};
```

**Ejemplo con Axios:**

```javascript
import axios from "axios";

const uploadToCloudinary = async (file, signatureData) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("signature", signatureData.signature);
  formData.append("timestamp", signatureData.timestamp);
  formData.append("api_key", signatureData.api_key);
  formData.append("public_id", signatureData.public_id);
  formData.append("folder", signatureData.folder);

  const { data } = await axios.post(signatureData.upload_url, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return data;
};
```

---

### 3. Enviar Referencias a Django

**Endpoint:** `POST /api/v1/catalog/treatments/` (o `PATCH` para actualizar)

**Content-Type:** `application/json` ⚠️ **NO** `multipart/form-data`

**Request Body:**

```json
{
  "title": "Treatment Name",
  "slug": "treatment-name",
  "category": "uuid-category-id",
  "requires_zones": false,
  "benefits_image_ref": {
    "public_id": "catalog/items/benefits/img-123"
  },
  "recommended_image_ref": {
    "public_id": "catalog/items/recommended/img-456"
  },
  "media_items": [
    {
      "public_id": "catalog/treatments/video-789",
      "resource_type": "video",
      "alt_text": "Video demostrativo del tratamiento"
    },
    {
      "public_id": "catalog/treatments/image-101",
      "resource_type": "image"
    }
  ]
}
```

**Campos de Media:**

| Campo                   | Tipo               | Descripción                                 |
| ----------------------- | ------------------ | ------------------------------------------- |
| `media_items`           | Array              | Galería de media (videos/imágenes) ordenada |
| `benefits_image_ref`    | Object/String/null | Imagen de beneficios (single)               |
| `recommended_image_ref` | Object/String/null | Imagen recomendada (single)                 |

**Formato de `media_items`:**

- `{"public_id": "...", "resource_type": "image\|video"}` - Agregar nuevo item
- `{"public_id": "...", "resource_type": "...", "alt_text": "..."}` - Con texto alternativo
- `{"id": "existing-uuid"}` - Mantener item existente en esta posición
- `{"id": "existing-uuid", "remove": true}` - Eliminar item existente

**Formato de image refs:**

- `{"public_id": "catalog/items/benefits/img-123"}` - Establecer imagen
- `"catalog/items/benefits/img-123"` - String directo también válido
- `null` - Limpiar imagen (set to null)

---

## Operaciones de Actualización

### Reordenar Media Existente

```json
{
  "media_items": [
    { "id": "existing-uuid-2" }, // Mover segundo a primero
    { "id": "existing-uuid-1" } // Mover primero a segundo
  ]
}
```

### Agregar Nuevo + Mantener Existente

```json
{
  "media_items": [
    { "id": "existing-uuid-1" },
    { "public_id": "catalog/treatments/new-video", "resource_type": "video" },
    { "id": "existing-uuid-2" }
  ]
}
```

### Eliminar Item Específico

```json
{
  "media_items": [{ "id": "uuid-to-delete", "remove": true }]
}
```

### Limpiar Toda la Galería

```json
{
  "media_items": []
}
```

### Reemplazar Imagen de Beneficios

```json
{
  "benefits_image_ref": {
    "public_id": "catalog/items/benefits/new-img"
  }
}
```

### Limpiar Imagen (Set to Null)

```json
{
  "benefits_image_ref": null
}
```

---

## Contextos de Upload Disponibles

Para listar todos los contextos disponibles dinámicamente:

**Endpoint:** `GET /api/v1/catalog/upload/contexts/`

**Response:**

```json
{
  "contexts": {
    "catalog_treatment_media": "catalog/treatments",
    "catalog_combo_media": "catalog/combos",
    "catalog_journey_media": "catalog/journeys",
    "catalog_items_benefits": "catalog/items/benefits",
    "catalog_items_recommended": "catalog/items/recommended",
    "catalog_categories": "catalog/categories",
    "waxing_content": "waxing/content",
    "waxing_sections": "waxing/sections",
    "waxing_area_categories": "waxing/area_categories",
    "waxing_areas": "waxing/areas",
    "waxing_packs": "waxing/packs"
  }
}
```

### Tabla de Contextos

| Contexto                    | Prefijo Cloudinary          | Usado Para                      | Modelo                  |
| --------------------------- | --------------------------- | ------------------------------- | ----------------------- |
| `catalog_treatment_media`   | `catalog/treatments`        | Galería de treatments           | Treatment               |
| `catalog_combo_media`       | `catalog/combos`            | Galería de combos               | Combo                   |
| `catalog_journey_media`     | `catalog/journeys`          | Galería de journeys             | Journey                 |
| `catalog_items_benefits`    | `catalog/items/benefits`    | Imágenes de beneficios          | Treatment/Combo/Journey |
| `catalog_items_recommended` | `catalog/items/recommended` | Imágenes recomendadas           | Treatment/Combo/Journey |
| `catalog_categories`        | `catalog/categories`        | Imágenes de categorías          | Category                |
| `waxing_content`            | `waxing/content`            | Imágenes de waxing content      | WaxingContent           |
| `waxing_sections`           | `waxing/sections`           | Imágenes de secciones           | Section                 |
| `waxing_area_categories`    | `waxing/area_categories`    | Imágenes de categorías de áreas | AreaCategory            |
| `waxing_areas`              | `waxing/areas`              | Imágenes de áreas               | Area                    |
| `waxing_packs`              | `waxing/packs`              | Imágenes de packs               | Pack                    |

---

## Validaciones Backend

Django validará automáticamente que:

✅ El `public_id` esté dentro de los prefijos permitidos para ese modelo
✅ El `resource_type` sea válido (`"image"` o `"video"`)
✅ Las referencias a items existentes (`id`) pertenezcan al recurso correcto
✅ No se intenten mezclar items de otros recursos

Si valida incorrectamente, recibirás un error `400 Bad Request` con detalles.

---

## Ejemplo Completo: Workflow de Creación

```javascript
// ==========================================
// PASO 1: Obtener firma para cada archivo
// ==========================================

const getUploadSignature = async (context, resourceType) => {
  const response = await fetch("/api/v1/catalog/upload/sign/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({ context, resource_type: resourceType }),
  });

  if (!response.ok) {
    throw new Error("Failed to get upload signature");
  }

  return await response.json();
};

// ==========================================
// PASO 2: Subir archivos a Cloudinary
// ==========================================

const uploadFileToCloudinary = async (file, context, resourceType) => {
  // Get signature
  const signature = await getUploadSignature(context, resourceType);

  // Upload to Cloudinary
  const formData = new FormData();
  formData.append("file", file);
  formData.append("signature", signature.signature);
  formData.append("timestamp", signature.timestamp);
  formData.append("api_key", signature.api_key);
  formData.append("public_id", signature.public_id);
  formData.append("folder", signature.folder);

  const response = await fetch(signature.upload_url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Cloudinary upload failed");
  }

  return await response.json();
};

// ==========================================
// PASO 3: Crear treatment con referencias
// ==========================================

const createTreatment = async (
  treatmentData,
  videoFile,
  imageFile,
  benefitsImageFile,
) => {
  // Upload all files first
  const videoUpload = await uploadFileToCloudinary(
    videoFile,
    "catalog_treatment_media",
    "video",
  );

  const imageUpload = await uploadFileToCloudinary(
    imageFile,
    "catalog_treatment_media",
    "image",
  );

  const benefitsUpload = await uploadFileToCloudinary(
    benefitsImageFile,
    "catalog_items_benefits",
    "image",
  );

  // Create treatment with references
  const response = await fetch("/api/v1/catalog/treatments/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({
      ...treatmentData,
      benefits_image_ref: {
        public_id: benefitsUpload.public_id,
      },
      media_items: [
        {
          public_id: videoUpload.public_id,
          resource_type: videoUpload.resource_type,
          alt_text: "Video demostrativo",
        },
        {
          public_id: imageUpload.public_id,
          resource_type: imageUpload.resource_type,
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to create treatment");
  }

  return await response.json();
};

// ==========================================
// USO
// ==========================================

const handleSubmit = async (formData, files) => {
  try {
    const treatment = await createTreatment(
      {
        title: formData.title,
        slug: formData.slug,
        category: formData.categoryId,
        requires_zones: formData.requiresZones,
      },
      files.video,
      files.image,
      files.benefitsImage,
    );

    console.log("Treatment created:", treatment);
  } catch (error) {
    console.error("Error creating treatment:", error);
  }
};
```

---

## Migración del Código Existente

### ❌ Antes (Multipart - NO usar más)

```javascript
const formData = new FormData();
formData.append("title", "Treatment");
formData.append("category", categoryId);
formData.append("uploaded_media", videoFile);
formData.append("uploaded_media", imageFile);

await fetch("/api/v1/catalog/treatments/", {
  method: "POST",
  body: formData, // ❌ multipart/form-data
});
```

### ✅ Después (JSON + Cloudinary)

```javascript
// 1. Upload each file to Cloudinary first
const videoRef = await uploadFileToCloudinary(
  videoFile,
  "catalog_treatment_media",
  "video",
);
const imageRef = await uploadFileToCloudinary(
  imageFile,
  "catalog_treatment_media",
  "image",
);

// 2. Send only references as JSON
await fetch("/api/v1/catalog/treatments/", {
  method: "POST",
  headers: {
    "Content-Type": "application/json", // ✅ JSON
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({
    title: "Treatment",
    category: categoryId,
    media_items: [
      {
        public_id: videoRef.public_id,
        resource_type: videoRef.resource_type,
      },
      {
        public_id: imageRef.public_id,
        resource_type: imageRef.resource_type,
      },
    ],
  }),
});
```

---

## Manejo de Errores

### Error: Invalid Context

```json
{
  "error": "Invalid context. Allowed: ['catalog_treatment_media', 'catalog_combo_media', ...]"
}
```

**Solución:** Verifica que estés usando un contexto válido de la lista. Puedes obtener la lista con `GET /api/v1/catalog/upload/contexts/`.

### Error: Invalid Public ID Prefix

```json
{
  "media_items": [
    {
      "public_id": "public_id 'hacker/malicious/file' is not allowed"
    }
  ]
}
```

**Solución:** El `public_id` debe comenzar con uno de los prefijos permitidos para ese modelo. Usa el `public_id` generado por el endpoint `/upload/sign/`.

### Error: Media Item Does Not Belong to Treatment

```json
{
  "media_items": [
    {
      "id": "Media item does not belong to this treatment"
    }
  ]
}
```

**Solución:** No puedes referenciar items de media de otro treatment. Solo usa IDs de items que pertenezcan al treatment que estás editando.

### Error: Cloudinary Upload Failed

Si la subida a Cloudinary falla:

1. Verifica que la firma no haya expirado (expira en 1 hora)
2. Verifica que los parámetros sean exactamente los retornados por `/upload/sign/`
3. Verifica el tamaño del archivo (límite: 100 MB)
4. Verifica el formato del archivo (debe coincidir con `allowed_formats`)

---

## Consideraciones de UX

### Progress Indicators

Ya que la subida a Cloudinary puede tomar tiempo (especialmente videos grandes), considera mostrar:

```javascript
const uploadWithProgress = async (file, context, resourceType, onProgress) => {
  const signature = await getUploadSignature(context, resourceType);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status === 200) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(`Upload failed: ${xhr.statusText}`));
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Upload failed")));

    const formData = new FormData();
    formData.append("file", file);
    formData.append("signature", signature.signature);
    formData.append("timestamp", signature.timestamp);
    formData.append("api_key", signature.api_key);
    formData.append("public_id", signature.public_id);
    formData.append("folder", signature.folder);

    xhr.open("POST", signature.upload_url);
    xhr.send(formData);
  });
};

// Usage
await uploadWithProgress(file, context, resourceType, (progress) => {
  console.log(`Upload progress: ${progress}%`);
  // Update UI
});
```

### Validación de Archivos en Frontend

Valida antes de subir para mejor UX:

```javascript
const validateFile = (
  file,
  maxSizeMB = 100,
  allowedFormats = ["mp4", "mov", "jpg", "png"],
) => {
  // Size check
  const maxSizeBytes = maxSizeMB * 1024 * 1024;
  if (file.size > maxSizeBytes) {
    throw new Error(`File too large. Max size: ${maxSizeMB}MB`);
  }

  // Format check
  const ext = file.name.split(".").pop().toLowerCase();
  if (!allowedFormats.includes(ext)) {
    throw new Error(`Invalid format. Allowed: ${allowedFormats.join(", ")}`);
  }

  return true;
};
```

### Retry Logic

Para uploads grandes, considera implementar retry logic:

```javascript
const uploadWithRetry = async (file, context, resourceType, maxRetries = 3) => {
  let lastError;

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await uploadFileToCloudinary(file, context, resourceType);
    } catch (error) {
      lastError = error;
      console.warn(`Upload attempt ${i + 1} failed, retrying...`);
      await new Promise((resolve) => setTimeout(resolve, 1000 * (i + 1)));
    }
  }

  throw lastError;
};
```

---

## Recursos Adicionales

- **Cloudinary Upload API Docs:** https://cloudinary.com/documentation/upload_images
- **Signed Upload Tutorial:** https://cloudinary.com/documentation/upload_images#signed_uploads
- **Backend Source:** `apps/shared/cloudinary/upload.py`
- **Serializers Source:** `apps/catalog/serializers/cloudinary_mixin.py`

---

## Preguntas Frecuentes

### ¿Por qué cambiar a upload directo?

El envío de archivos grandes a través de Django/Cloud Run causaba errores `413 Content Too Large` porque los archivos pasaban por múltiples capas (cliente → proxy → Cloud Run → Django → Cloudinary). El upload directo elimina estos intermediarios.

### ¿Los archivos viejos se limpian automáticamente?

Sí, cuando reemplazas una imagen o media item, Django intentará eliminar el archivo viejo de Cloudinary automáticamente mediante signals.

### ¿Puedo seguir usando multipart/form-data?

No. Los ViewSets ahora solo aceptan `Content-Type: application/json`. Debes migrar al nuevo flujo JSON + Cloudinary.

### ¿Qué pasa si el upload a Cloudinary falla después de obtener la firma?

La firma expira en 1 hora. Si el upload falla, simplemente obtén una nueva firma y reintenta. El `public_id` generado es único cada vez.

### ¿Puedo subir múltiples archivos en paralelo?

Sí, puedes usar `Promise.all()` para subir múltiples archivos simultáneamente a Cloudinary:

```javascript
const [video, image1, image2] = await Promise.all([
  uploadFileToCloudinary(videoFile, "catalog_treatment_media", "video"),
  uploadFileToCloudinary(imageFile1, "catalog_treatment_media", "image"),
  uploadFileToCloudinary(imageFile2, "catalog_treatment_media", "image"),
]);
```

### ¿Los public_ids son únicos?

Sí, el backend genera UUIDs únicos para cada firma. No hay riesgo de colisión.

---

## Changelog

### 2026-03-26 - Primera versión

- Implementación inicial de upload directo a Cloudinary
- Migración de Treatment, Combo, Journey, WaxingContent serializers
- Documentación completa para frontend
