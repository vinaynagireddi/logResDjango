from django.shortcuts import render,redirect
from django.http import JsonResponse, HttpResponse
from django.views import View
import bcrypt
from pymongo import MongoClient
import re
from django.template.loader import render_to_string
import pdfkit
import csv
from django.core.paginator import Paginator
from io import BytesIO, StringIO
from django.core.mail import EmailMessage


client = MongoClient("mongodb://localhost:27017")
db = client["offDatabase"]
collection = db["employee"]


def welcome(request):
    return render(request, "welcome.html")


class register(View):
    def get(self, request):
        return render(request, "register.html")

    def post(self, request):
        if request.method == "POST":
            username = request.POST.get("username")
            email = request.POST.get("email")
            phnumber = request.POST.get("phnumber")
            password = request.POST.get("password")
            response = {}
            if not username or not email or not phnumber or not password:
                response["error"] = "All fields are required!"
            email_regex = r"^[a-zA-Z0-9.]+@[a-zA-Z0-9.]+\.[a-zA-Z]{2,}$"
            if email and not re.match(email_regex, email):
                response["email_error"] = "Invalid email format!"
            if phnumber and not re.match(r"^\d{10}$", phnumber):
                response["phnumber_error"] = (
                    "Phone number must contain exactly 10 digits!"
                )
            if collection.find_one({"username": username}):
                response["username_error"] = "Username already exists!"
            if collection.find_one({"email": email}):
                response["email_exists_error"] = "Email already exists!"
            if collection.find_one({"phnumber": phnumber}):
                response["phnumber_exists_error"] = "Phone number already exists!"
            if response:
                return JsonResponse(response, status=400)
            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            try:
                collection.insert_one(
                    {
                        "username": username,
                        "email": email,
                        "phnumber": phnumber,
                        "password": hashed_password.decode("utf-8"),
                    }
                )
                response["message"] = "User added successfully!"
                response["user"] = {
                    "username": username,
                    "email": email,
                    "phnumber": phnumber,
                }
                return JsonResponse(response, status=201)
            except Exception as e:
                response["database_error"] = "Database error: " + str(e)
                return JsonResponse(response, status=500)


class login(View):
    def get(self, request):
        return render(request, "login.html")

    def post(self, request):
        email = request.POST.get("email")
        password = request.POST.get("password")
        if not email or not password:
            return JsonResponse(
                {"success": False, "error": "Both fields are required!"}, status=400
            )
        user = collection.find_one({"email": email})
        if not user:
            return JsonResponse(
                {"success": False, "error": "User not found!"}, status=400
            )
        stored_password = user.get("password")
        if not stored_password:
            return JsonResponse(
                {"success": False, "error": "Password not set for this user!"},
                status=400,
            )
        if isinstance(stored_password, str):
            stored_password = stored_password.encode("utf-8")
        if bcrypt.checkpw(password.encode("utf-8"), stored_password):
            request.session["user_id"] = str(user["_id"])
            return JsonResponse({"success": True, "message": "Login successful!"})
        else:
            return JsonResponse(
                {"success": False, "error": "Invalid password!"}, status=400
            )


class Demodb(View):
    def get(self, request):
        
        if not request.session.get("user_id"):
            # Redirect to login or return unauthorized
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": "Unauthorized"}, status=401)
            return redirect("/login/")
        employees_list = list(
            collection.find({}, {"_id": 0, "username": 1, "email": 1, "phnumber": 1})
        )

        records_per_page = request.GET.get("records", 2)
        try:
            records_per_page = int(records_per_page)
        except ValueError:
            records_per_page = 2

        paginator = Paginator(employees_list, records_per_page)
        page_number = request.GET.get("page", 1)
        employees = paginator.get_page(page_number)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            employees_data = [
                {
                    "username": emp["username"],
                    "email": emp["email"],
                    "phnumber": emp["phnumber"],
                }
                for emp in employees
            ]
            return JsonResponse(
                {
                    "employees": employees_data,
                    "has_previous": employees.has_previous(),
                    "has_next": employees.has_next(),
                    "previous_page_number": (
                        employees.previous_page_number()
                        if employees.has_previous()
                        else None
                    ),
                    "next_page_number": (
                        employees.next_page_number() if employees.has_next() else None
                    ),
                    "current_page": employees.number,
                    "total_pages": employees.paginator.num_pages,
                }
            )
        return render(request, "main.html", {"employees": employees})

class Download(View):
    def get(self,request):
        employees=collection.find({},{"_id":0,"username" : 1,"email":1,"phnumber":1})
        html=render_to_string("pdf_template.html",{"employees":employees})
        pdf=pdfkit.from_string(html,False)
        response= HttpResponse(pdf,content_type="application/pdf")
        # response['Content-Disposition']='attachment;filename="user.pdf"'
        return  response