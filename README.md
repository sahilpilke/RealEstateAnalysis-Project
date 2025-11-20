
# Real Estate Data Analyzer (Full Stack Project)

This project is a full‑stack real estate data analyzer built using **Django (Backend)** and **React (Frontend)**.
It allows users to input natural language queries and generates:

- 📌 AI‑enhanced summary  
- 📈 Interactive charts (Price & Demand trends)  
- 🧾 Data table view  
- 📥 Download filtered data as Excel (XLSX)  
- 🧠 Optional LLM integration using Grok (xAI)

---

## 🚀 Live Deployment Links

### 🌐 **Frontend (Vercel)**
👉 https://real-estate-analysis-project.vercel.app/

### 🖥 **Backend (Render)**
👉 https://realestate-backend-soou.onrender.com/

---

## 🚀 Tech Stack

### **Frontend**
- React.js  
- Bootstrap  
- Recharts  

### **Backend**
- Django REST Framework  
- Pandas / NumPy  
- OpenPyXL  

---

## 📂 Project Structure

```
RealEstate_Project/
│── realestate_backend/        # Django backend
│── realestate_frontend/       # React frontend
│── README.md
```

---

## 🔧 Setup Instructions

### 1️⃣ Backend Setup (Django)

```
cd realestate_backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Backend runs at:  
👉 **http://localhost:8000**

---

### 2️⃣ Frontend Setup (React)

```
cd realestate_frontend
npm install
npm start
```

Frontend runs at:  
👉 **http://localhost:3000**

---

## ⭐ Features

- Search real estate insights using plain English  
- Auto‑detected areas and trends  
- Two charts per area (Price vs Demand)  
- Recent queries and suggested prompts  
- Download filtered Excel data  
- Clean dark UI  

---

## 📥 Excel Download API

Endpoint:

```
POST /api/download-xlsx/
```

Payload:

```json
{
  "table_data": [...]
}
```

Returns:  
✔ Excel file (`filtered_data.xlsx`)

---

## 📌 Deployment Notes

- Backend deployed on **Render**  
- Frontend deployed on **Vercel**  
- Enable CORS (`CORS_ALLOW_ALL_ORIGINS = True`) for development  

---

## 🤝 Contribution

Pull requests are welcome!

---

## 📄 License

This project is for assignment purposes and not licensed for commercial use.
