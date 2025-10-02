import random
import io
from django.db import IntegrityError
from django.http import HttpResponseRedirect, FileResponse, HttpResponseForbidden
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from QPaperGeneration.models import User, QPattern, Subject, Topic

# Create your views here.

@login_required(login_url='login')
def index(request):
    return render(request, "index.html",{
        "subjects": Subject.objects.all()
    })


def login_view(request):
    if request.method == "POST":
        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {username}!")
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "login.html")

def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        messages.success(request, f"Account created successfully! Welcome, {username}!")
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "register.html")

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return HttpResponseRedirect(reverse("index"))

def myquestions(request):
    if request.method == "POST":
        user = request.user
        subject = request.POST["subject"]
        topic = request.POST["topic"]
        marks = request.POST["marks"]
        difficulty = request.POST["difficulty"]
        question = request.POST["question"]
        answer = request.POST["answer"]

        try:
            # SIMPLIFIED: No created_by field needed
            cursub, subcr = Subject.objects.get_or_create(name=subject)
            
            # SIMPLIFIED: No created_by field needed
            curtop, topcr = Topic.objects.get_or_create(
                name=topic,
                sub=cursub
            )
            
            qamodel = QPattern.objects.create(
                user=user, 
                topic=curtop, 
                subject=cursub,
                question=question, 
                answer=answer, 
                marks=marks, 
                difficulty=difficulty
            )
            qamodel.save()
            
            messages.success(request, "✅ Question added successfully!")
            return HttpResponseRedirect(reverse("myquestions"))
            
        except Exception as e:
            messages.error(request, f"❌ Error adding question: {str(e)}")
            return HttpResponseRedirect(reverse("myquestions"))
            
    elif request.method == "GET":
        questionandanswers = QPattern.objects.all()
        return render(request, "myquestions.html",{
            "questions": questionandanswers,
        })
    else:
        return HttpResponseForbidden("Method not allowed")

def papergen1(request):
    if request.method == "POST":
        checkboxstatus = False
        if request.POST.get('marksboxcheck', False) == 'on':
            checkboxstatus = True
        
        # Validate if there are enough questions for the selected paper type
        subsel = request.POST["subsel"]
        ptype = request.POST["ptype"]
        topics = Topic.objects.filter(sub=Subject.objects.get(pk=subsel))
        
        # Count available questions
        total_questions = QPattern.objects.filter(subject_id=subsel).count()
        two_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=2).count()
        five_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=5).count()
        ten_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=10).count()
        
        if ptype == '1' and (two_mark_questions < 6 or five_mark_questions < 4):
            messages.warning(request, f"⚠️ Insufficient questions for IA Paper. Required: 6+ 2-mark questions (have {two_mark_questions}), 4+ 5-mark questions (have {five_mark_questions})")
        elif ptype == '2' and (five_mark_questions < 4 or ten_mark_questions < 10):
            messages.warning(request, f"⚠️ Insufficient questions for Semester Paper. Required: 4+ 5-mark questions (have {five_mark_questions}), 10+ 10-mark questions (have {ten_mark_questions})")
        else:
            messages.info(request, f"📊 Available: {two_mark_questions} 2-mark, {five_mark_questions} 5-mark, {ten_mark_questions} 10-mark questions")
        
        return render(request, "index2.html",{
            "heading": request.POST["heading"],
            "extradetails": request.POST["extradetails"],
            "marksboxcheck": checkboxstatus,
            "ptype": ptype,
            "subsel": subsel,
            "topics": topics
        })
    else:
        return HttpResponseForbidden("Method not allowed")

def papergen2(request):
    try:
        title = request.POST["heading"]
        subTitle = request.POST.get("extradetails", "")
        marksboxcheck = request.POST["marksboxcheck"]
        topics = request.POST.getlist('topics')
        topics = [eval(i) for i in topics]
        cos = request.POST.getlist('cos')
        cos = [eval(i) for i in cos]

        twomqs = []
        sevmqs = []
        tens = []
        
        # Collect questions for selected topics
        for topic in topics:
            topic_obj = Topic.objects.filter(id=topic).first()
            if topic_obj:
                twomqs.extend(list(QPattern.objects.filter(marks=2, topic=topic_obj)))
                sevmqs.extend(list(QPattern.objects.filter(marks=5, topic=topic_obj)))
                tens.extend(list(QPattern.objects.filter(marks=10, topic=topic_obj)))

        # Prepare the questions based on the new format
        qLines = []
        i = 1
        
        print("number of 2 marks questions: ", len(twomqs))
        print("number of 5 marks questions: ", len(sevmqs))
        print("number of 10 marks questions: ", len(tens))

        ptype = request.POST["ptype"]
        
        if ptype == '1':  # IA Paper
            qLines.append("Time : 1 Hour")
            qLines.append("Max Marks : 20")
            qLines.append("")
            qLines.append("1. Attempt the following questions:")
            qLines.append("2. Avoid using any unfair means during the paper.")
            qLines.append("")

            # Q1: Any five questions from 6 (2 marks each)
            if len(twomqs) >= 6:
                qLines.append("Question 1 : Any five questions - 2 marks each")
                qLines.append(f"(Choose 5 from the following 6 questions)")
                twolist = random.sample(twomqs, 6)
                for tq in twolist:
                    qLines.append(f"Q.{i} " + tq.question)
                    i += 1
            else:
                qLines.append("Question 1 : Insufficient 2-mark questions available")
                qLines.append(f"(Available: {len(twomqs)}, Required: 6)")

            qLines.append("")  # Add spacing

            # Q2: Any one question from 2 (5 marks)
            if len(sevmqs) >= 2:
                qLines.append("Question 2 : Any one question - 5 marks")
                qLines.append(f"(Choose 1 from the following 2 questions)")
                sevlist = random.sample(sevmqs, 2)
                qLines.append(f"Q.{i} " + sevlist[0].question)
                qLines.append(f"Q.{i+1} " + sevlist[1].question)
                i += 2
            else:
                qLines.append("Question 2 : Insufficient 5-mark questions available")
                qLines.append(f"(Available: {len(sevmqs)}, Required: 2)")

            qLines.append("")  # Add spacing

            # Q3: Any one question from 2 (5 marks)
            if len(sevmqs) >= 4:
                qLines.append("Question 3 : Any one question - 5 marks")
                qLines.append(f"(Choose 1 from the following 2 questions)")
                # Use different questions than Q2
                remaining_sevmqs = [q for q in sevmqs if q not in sevlist]
                if len(remaining_sevmqs) >= 2:
                    new_sevlist = random.sample(remaining_sevmqs, 2)
                    qLines.append(f"Q.{i} " + new_sevlist[0].question)
                    qLines.append(f"Q.{i+1} " + new_sevlist[1].question)
                    i += 2
                else:
                    qLines.append("Question 3 : Not enough unique 5-mark questions available")
            else:
                qLines.append("Question 3 : Insufficient 5-mark questions available")
                qLines.append(f"(Available: {len(sevmqs)}, Required: 4 for all sections)")
        
        elif ptype == '2':  # Semester papers
            qLines.append("Time : 3 Hours")
            qLines.append("Max Marks : 100")
            qLines.append("")
            qLines.append("1. Answer all questions.")
            qLines.append("2. All questions carry equal marks.")
            qLines.append("3. Attempt any 3 questions from Q2 to Q6.")
            qLines.append("4. Avoid using any unfair means during the paper.")
            qLines.append("")

            # Q1: Compulsory question (5 marks each)
            if len(sevmqs) >= 4:
                qLines.append("Question 1 : Compulsory questions - 5 marks each")
                comp_qs = random.sample(sevmqs, 4)
                for tq in comp_qs:
                    qLines.append(f"Q.{i} " + tq.question)
                    i += 1
            else:
                qLines.append("Question 1 : Insufficient 5-mark questions available")
                qLines.append(f"(Available: {len(sevmqs)}, Required: 4)")

            qLines.append("")  # Add spacing

            # Q2-Q6: Each worth 20 marks (2 sub-questions for 10 marks each)
            if len(tens) >= 10:
                main_qs = random.sample(tens, 10)
                questions_data = [
                    ("Question 2", main_qs[0:2]),
                    ("Question 3", main_qs[2:4]),
                    ("Question 4", main_qs[4:6]),
                    ("Question 5", main_qs[6:8]),
                    ("Question 6", main_qs[8:10])
                ]
                
                for q_title, q_pair in questions_data:
                    qLines.append(f"{q_title} : Answer both sub-questions (10 marks each) - Total 20 marks")
                    qLines.append(f"Q.{i} " + q_pair[0].question)
                    qLines.append(f"Q.{i+1} " + q_pair[1].question)
                    i += 2
                    qLines.append("")
            else:
                qLines.append("Insufficient 10-mark questions for semester paper")
                qLines.append(f"(Available: {len(tens)}, Required: 10)")
        
        else:
            qLines.append("Invalid paper type selected")

        # Generate PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        p.setFont("Times-Roman", 24)
        p.setTitle(title)
        p.drawCentredString(300, 770, title)
        p.setFont("Times-Roman", 16)
        p.drawCentredString(290, 720, subTitle)
        p.line(30, 710, 550, 710)
        p.setFont("Times-Roman", 12)
        text = p.beginText(40, 680)
        for line in qLines:
            text.textLine(line)
        p.drawText(text)
        p.showPage()
        p.save()
        buffer.seek(0)
        
        messages.success(request, "📄 Question paper generated successfully!")
        return FileResponse(buffer, as_attachment=True, filename='QuestionPaper.pdf')
    
    except Exception as e:
        print(f"Error in papergen2: {str(e)}")
        messages.error(request, f"❌ Error generating question paper: {str(e)}")
        
        # Return a user-friendly error response
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        p.setFont("Times-Roman", 16)
        p.drawCentredString(300, 400, "Error Generating Question Paper")
        p.setFont("Times-Roman", 12)
        p.drawCentredString(300, 380, f"Error: {str(e)}")
        p.drawCentredString(300, 360, "Please check if you have enough questions in your database.")
        p.showPage()
        p.save()
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename='Error_Report.pdf')