### Abstract / System Overview
The system, RevFit, implements an automated health management platform designed for fitness tracking and nutritional planning. The primary objective of the application is to execute real-time fitness pose estimation, exercise classification, and personalized diet and workout recommendations through integrated machine learning pipelines.

### System Architecture
* **Frontend:** Flutter (Cross-platform framework supporting mobile, web, and desktop interfaces)
* **Backend:** FastAPI (Python-based asynchronous server architecture)
* **Machine Learning / Vision:** PyTorch, OpenCV, MediaPipe
* **External Integrations:** Spoonacular API (for macronutrient-based recipe mapping)
* **Cloud/Deployment:** Uvicorn ASGI web server handling RESTful API requests and serving static files for annotated video outputs

### Methodology
The application integrates a 50/50 hybrid deep learning ensemble, utilizing VideoMAE (Vision Transformer) and X3D-M (3D Convolutional Neural Network), to classify exercises into a 20-class taxonomy. For biomechanical analysis, headless OpenCV and MediaPipe calculate skeletal angles and detect dynamic repetition counts via continuous video frame streams. Nutritional parameters are quantified utilizing the Mifflin-St Jeor equation to calculate Basal Metabolic Rate (BMR) and Total Daily Energy Expenditure (TDEE). The recommendation engine applies a content-based filtering algorithm, incorporating a user feedback memory mechanism with exponential preference decay to iteratively optimize workout routines and meal plans.

### Implementation & Usage
* **System Requirements:** Python environment for backend inference and API hosting; Flutter SDK for cross-platform client execution.
* **Technical Constraints:** Requires continuous asynchronous background processing to evaluate computationally intensive video streams and generate visual overlays without blocking the primary execution thread.
* **Operational Flows:** The client interface captures user biometric parameters and workout media, transmitting the payloads to the FastAPI endpoints. The backend computes skeletal assessments and macronutrient distributions, subsequently serving the formulated meal structures, workout splits, and annotated form-correction videos back to the graphical user interface.
