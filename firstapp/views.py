from django.shortcuts import render
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
        if not email or password:
            return JsonResponse("Please enter all fields")
        user = collection.find_one({"email": email})
        if not user:
            return JsonResponse("Invalid Email")
        if user:
            stored_pass = user.get("password")
            pass_word = bcrypt.checkpw(
                password.encode("utf-8"), stored_pass.encode("utf-8")
            )

        else:
            return JsonResponse("Invalid email")


class Demodb(View):
    def get(self, request):
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


class DownloadData(View):
    def get(self, request):
        employees = list(
            collection.find({}, {"_id": 0, "username": 1, "email": 1, "phnumber": 1})
        )
        file_format = request.GET.get("format")
        recipient_email = request.GET.get("email")

        if not recipient_email:
            return HttpResponse("Email address is required", status=400)

        if file_format == "csv":
            file_data, file_name, file_mimetype = self.generate_csv(employees)
        elif file_format == "pdf":
            file_data, file_name, file_mimetype = self.generate_pdf(employees)
        else:
            return HttpResponse("Invalid format", status=400)

        self.send_email(file_data, file_name, file_mimetype, recipient_email)
        return HttpResponse(f"Email sent successfully to {recipient_email}")

    def generate_pdf(self, employees):
        """Generate PDF file in memory"""
        html_content = render_to_string("pdf_template.html", {"employees": employees})
        pdf_data = pdfkit.from_string(html_content, False)  # Generate PDF binary data
        pdf_buffer = BytesIO(pdf_data)  # Convert to BytesIO

        return pdf_buffer, "employee_data.pdf", "application/pdf"

    def generate_csv(self, employees):
        """Generate CSV file in memory"""
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["Username", "Email", "Phone Number"])

        for emp in employees:
            writer.writerow([emp["username"], emp["email"], emp["phnumber"]])

        csv_buffer.seek(0)  # Move to start of file
        return BytesIO(csv_buffer.getvalue().encode()), "employee_data.csv", "text/csv"

    def send_email(self, file_data, file_name, file_mimetype, recipient_email):
        """Send an email with the file attached"""
        email_subject = "Employee Data Download"
        email_body = "Attached is the requested employee data."

        email = EmailMessage(
            subject=email_subject,
            body=email_body,
            from_email="vinaynagireddy222@gmail.com",  # Correct email format
            to=[recipient_email],
        )

        email.attach(file_name, file_data.getvalue(), file_mimetype)  # Attach file
        email.send()
