import random       
import io                         
import json                      
from django.http import JsonResponse 
from django.views.decorators.csrf import csrf_protect
from django.db import IntegrityError  
from django.http import HttpResponseRedirect, FileResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from django.utils import timezone
from django.db.models import Avg, Count, Sum

from QPaperGeneration.models import User, QPattern, Subject, Topic, StudentGeneratedPaper

# Create your views here.

@login_required(login_url='student_login')
def dashboard(request):
    """Main dashboard with role-based access cards"""
    context = {}
    
    # Add stats for admin
    if request.user.role == 'admin':
        context.update({
            'total_users': User.objects.count(),
            'total_questions': QPattern.objects.count(),
            'total_papers': QPattern.objects.filter(user=request.user).count(),
            'total_subjects': Subject.objects.count(),
        })
    
    return render(request, "dashboard.html", context)

@login_required(login_url='student_login')
def index(request):
    """Redirect to dashboard - keeping for backward compatibility"""
    return HttpResponseRedirect(reverse("dashboard"))

@login_required(login_url='student_login')
def admin_dashboard(request):
    """Admin-specific dashboard"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    # Admin statistics
    total_users = User.objects.count()
    total_staff = User.objects.filter(role='staff').count()
    total_students = User.objects.filter(role='student').count()
    total_questions = QPattern.objects.count()
    total_subjects = Subject.objects.count()
    
    # Recent activities
    recent_questions = QPattern.objects.all().order_by('-id')[:5]
    recent_users = User.objects.all().order_by('-date_joined')[:5]
    
    context = {
        'total_users': total_users,
        'total_staff': total_staff,
        'total_students': total_students,
        'total_questions': total_questions,
        'total_subjects': total_subjects,
        'recent_questions': recent_questions,
        'recent_users': recent_users,
    }
    
    return render(request, "admin_dashboard.html", context)

@login_required(login_url='student_login')
def user_management(request):
    """Admin user management page"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    # Get all users with their statistics
    users = User.objects.all().order_by('-date_joined')
    
    # Apply filters
    role_filter = request.GET.get('role', '')
    search_query = request.GET.get('search', '')
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) | 
            Q(email__icontains=search_query)
        )
    
    # Calculate user statistics
    total_users = users.count()
    staff_count = users.filter(role='staff').count()
    student_count = users.filter(role='student').count()
    admin_count = users.filter(role='admin').count()
    
    # Get recent activity (last login)
    active_today = users.filter(last_login__date=timezone.now().date()).count()
    
    # Pagination
    paginator = Paginator(users, 15)  # 15 users per page
    page_number = request.GET.get('page')
    users_page = paginator.get_page(page_number)
    
    context = {
        'users': users_page,
        'total_users': total_users,
        'staff_count': staff_count,
        'student_count': student_count,
        'admin_count': admin_count,
        'active_today': active_today,
        'role_filter': role_filter,
        'search_query': search_query,
    }
    
    return render(request, "user_management.html", context)

@login_required(login_url='student_login')
@csrf_protect
def create_user(request):
    """Create new user - admin only"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied. Admin privileges required.'})
    
    if request.method == "POST":
        try:
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            role = request.POST.get('role', 'student')
            
            # Validate required fields
            if not all([username, email, password]):
                return JsonResponse({'success': False, 'error': 'All fields are required.'})
            
            # Check if username already exists
            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'error': 'Username already taken.'})
            
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'Email already registered.'})
            
            # Create user
            user = User.objects.create_user(username, email, password)
            user.role = role
            user.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'User {username} created successfully as {role}.',
                'user_id': user.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error creating user: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@login_required(login_url='student_login')
@csrf_protect
def update_user(request, user_id):
    """Update user details - admin only"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied. Admin privileges required.'})
    
    try:
        user = get_object_or_404(User, id=user_id)
        
        if request.method == "POST":
            username = request.POST.get('username')
            email = request.POST.get('email')
            role = request.POST.get('role')
            is_active = request.POST.get('is_active') == 'true'
            
            # Check if username is taken by another user
            if username != user.username and User.objects.filter(username=username).exclude(id=user_id).exists():
                return JsonResponse({'success': False, 'error': 'Username already taken.'})
            
            # Check if email is taken by another user
            if email != user.email and User.objects.filter(email=email).exclude(id=user_id).exists():
                return JsonResponse({'success': False, 'error': 'Email already registered.'})
            
            # Update user
            user.username = username
            user.email = email
            user.role = role
            user.is_active = is_active
            user.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'User {username} updated successfully.'
            })
            
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error updating user: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@login_required(login_url='student_login')
@csrf_protect
def delete_user(request, user_id):
    """Delete user - admin only"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied. Admin privileges required.'})
    
    try:
        user = get_object_or_404(User, id=user_id)
        
        # Prevent admin from deleting themselves
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'You cannot delete your own account.'})
        
        username = user.username
        user.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'User {username} deleted successfully.'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error deleting user: {str(e)}'})

@login_required(login_url='student_login')
@csrf_protect
def reset_user_password(request, user_id):
    """Reset user password - admin only"""
    if request.user.role != 'admin':
        return JsonResponse({'success': False, 'error': 'Access denied. Admin privileges required.'})
    
    try:
        user = get_object_or_404(User, id=user_id)
        new_password = request.POST.get('new_password')
        
        if not new_password:
            return JsonResponse({'success': False, 'error': 'New password is required.'})
        
        user.set_password(new_password)
        user.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Password for {user.username} reset successfully.'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error resetting password: {str(e)}'})

@login_required(login_url='student_login')
def staff_dashboard(request):
    """Staff-specific dashboard"""
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, "Access denied. Staff privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    # Staff statistics
    my_questions = QPattern.objects.filter(user=request.user).count()
    total_questions = QPattern.objects.count()
    my_subjects = Subject.objects.all()
    
    # Recent questions by this staff
    recent_my_questions = QPattern.objects.filter(user=request.user).order_by('-id')[:5]
    
    context = {
        'my_questions': my_questions,
        'total_questions': total_questions,
        'subjects': my_subjects,
        'recent_questions': recent_my_questions,
    }
    
    return render(request, "staff_dashboard.html", context)

@login_required(login_url='student_login')
def student_dashboard(request):
    """Student-specific dashboard"""
    # Students can view all available question papers
    available_papers = QPattern.objects.all().order_by('-id')[:10]
    subjects = Subject.objects.all()
    
    # Get student's generated papers
    student_generated_papers = StudentGeneratedPaper.objects.filter(student=request.user).order_by('-created_at')[:5]
    
    context = {
        'available_papers': available_papers,
        'subjects': subjects,
        'student_generated_papers': student_generated_papers,
    }
    
    return render(request, "student_dashboard.html", context)

@login_required(login_url='student_login')
def student_generated_papers(request):
    """View for student to see their generated question papers"""
    student_generated_papers = StudentGeneratedPaper.objects.filter(student=request.user).order_by('-created_at')
    
    context = {
        'generated_papers': student_generated_papers,
    }
    
    return render(request, "student_generated_papers.html", context)

@login_required(login_url='student_login')
def student_download_paper(request, paper_id):
    """Download a single question paper as PDF for students"""
    try:
        # Get the specific question paper
        paper = get_object_or_404(QPattern, id=paper_id)
        
        # Generate PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Set up the PDF content
        p.setFont("Times-Bold", 20)
        p.drawCentredString(width/2, height-50, "QUESTION PAPER")
        p.setFont("Times-Roman", 12)
        p.drawCentredString(width/2, height-70, f"Subject: {paper.subject.name}")
        p.drawCentredString(width/2, height-85, f"Topic: {paper.topic.name}")
        
        # Draw line
        p.line(50, height-100, width-50, height-100)
        
        # Question details
        y_position = height - 120
        p.setFont("Times-Bold", 12)
        p.drawString(50, y_position, "Question Details:")
        y_position -= 20
        
        p.setFont("Times-Roman", 12)
        details = [
            f"Marks: {paper.marks}",
            f"Difficulty Level: {paper.difficulty}/5",
            f"Created by: {paper.user.username}",
            "",
            "Question:",
        ]
        
        for detail in details:
            p.drawString(50, y_position, detail)
            y_position -= 15
        
        # Add the question text with proper formatting
        y_position -= 10
        question_lines = simpleSplit(paper.question, "Times-Roman", 12, width-100)
        for line in question_lines:
            if y_position < 100:  # Check if we need a new page
                p.showPage()
                y_position = height - 50
                p.setFont("Times-Roman", 12)
            p.drawString(50, y_position, line)
            y_position -= 15
        
        # Add instructions
        y_position -= 20
        instructions = [
            "",
            "Instructions:",
            "• Answer the question completely",
            "• Show all working steps",
            "• Write neatly and legibly",
            "• Time: 60 minutes",
        ]
        
        for instruction in instructions:
            if y_position < 100:
                p.showPage()
                y_position = height - 50
                p.setFont("Times-Roman", 12)
            p.drawString(50, y_position, instruction)
            y_position -= 15
        
        p.showPage()
        p.save()
        buffer.seek(0)
        
        filename = f"Question_{paper.subject.name}_{paper.id}.pdf"
        messages.success(request, "📄 Question paper downloaded successfully!")
        return FileResponse(buffer, as_attachment=True, filename=filename)
        
    except Exception as e:
        messages.error(request, f"❌ Error generating PDF: {str(e)}")
        return HttpResponseRedirect(reverse("student_dashboard"))
    
@login_required(login_url='student_login')
def analytics_dashboard(request):
    """Admin analytics dashboard with detailed statistics"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    try:
        # User Statistics
        total_users = User.objects.count()
        users_today = User.objects.filter(date_joined__date=timezone.now().date()).count()
        users_this_week = User.objects.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=7)).count()
        users_this_month = User.objects.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=30)).count()
        
        # Role Distribution
        role_distribution = {
            'students': User.objects.filter(role='student').count(),
            'staff': User.objects.filter(role='staff').count(),
            'admins': User.objects.filter(role='admin').count(),
        }
        
        # Question Statistics
        total_questions = QPattern.objects.count()
        
        # Since QPattern doesn't have created_at, we'll use total counts
        questions_today = total_questions  # Placeholder
        questions_this_week = total_questions  # Placeholder
        questions_this_month = total_questions  # Placeholder
        
        # Marks Distribution
        marks_distribution = {
            '2_marks': QPattern.objects.filter(marks=2).count(),
            '5_marks': QPattern.objects.filter(marks=5).count(),
            '10_marks': QPattern.objects.filter(marks=10).count(),
        }
        
        # Difficulty Distribution
        difficulty_distribution = {}
        for i in range(1, 6):
            difficulty_distribution[f'level_{i}'] = QPattern.objects.filter(difficulty=i).count()
        
        # CORRECTED: Subject Statistics - Use the correct related_name 'sub'
        subjects = Subject.objects.annotate(
            question_count=Count('sub'),  # Use 'sub' which is the related_name from QPattern
            avg_difficulty=Avg('sub__difficulty'),
            avg_marks=Avg('sub__marks')
        ).order_by('-question_count')
        
        # Top Contributors (Users with most questions)
        top_contributors = User.objects.annotate(
            question_count=Count('usr')  # Use 'usr' which is the related_name from QPattern
        ).filter(question_count__gt=0).order_by('-question_count')[:10]
        
        # Recent Activity Timeline (last 7 days) - Using StudentGeneratedPaper created_at
        recent_activity = []
        for i in range(6, -1, -1):
            date = timezone.now().date() - timezone.timedelta(days=i)
            users_count = User.objects.filter(date_joined__date=date).count()
            papers_count = StudentGeneratedPaper.objects.filter(created_at__date=date).count()
            recent_activity.append({
                'date': date.strftime('%Y-%m-%d'),
                'display_date': date.strftime('%b %d'),
                'users': users_count,
                'questions': papers_count,  # Using papers as activity indicator
            })
        
        # System Performance Metrics
        active_users_today = User.objects.filter(last_login__date=timezone.now().date()).count()
        
        # Paper Generation Statistics
        total_papers_generated = StudentGeneratedPaper.objects.count()
        papers_today = StudentGeneratedPaper.objects.filter(created_at__date=timezone.now().date()).count()
        papers_this_week = StudentGeneratedPaper.objects.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count()
        papers_this_month = StudentGeneratedPaper.objects.filter(created_at__gte=timezone.now() - timezone.timedelta(days=30)).count()
        
        # Paper Generation by Role
        student_papers = StudentGeneratedPaper.objects.filter(student__role='student').count()
        staff_papers = StudentGeneratedPaper.objects.filter(student__role='staff').count()
        admin_papers = StudentGeneratedPaper.objects.filter(student__role='admin').count()
        
        # Calculate percentages
        student_percentage = (role_distribution['students'] / total_users * 100) if total_users > 0 else 0
        staff_percentage = (role_distribution['staff'] / total_users * 100) if total_users > 0 else 0
        admin_percentage = (role_distribution['admins'] / total_users * 100) if total_users > 0 else 0
        
        context = {
            # User Stats
            'total_users': total_users,
            'users_today': users_today,
            'users_this_week': users_this_week,
            'users_this_month': users_this_month,
            'role_distribution': role_distribution,
            'active_users_today': active_users_today,
            
            # Question Stats
            'total_questions': total_questions,
            'questions_today': questions_today,
            'questions_this_week': questions_this_week,
            'questions_this_month': questions_this_month,
            'marks_distribution': marks_distribution,
            'difficulty_distribution': difficulty_distribution,
            
            # Subject Stats
            'subjects': subjects,
            'top_contributors': top_contributors,
            
            # Activity Stats
            'recent_activity': recent_activity,
            'total_papers_generated': total_papers_generated,
            'papers_today': papers_today,
            'papers_this_week': papers_this_week,
            'papers_this_month': papers_this_month,
            
            # Paper Generation by Role
            'student_papers': student_papers,
            'staff_papers': staff_papers,
            'admin_papers': admin_papers,
            
            # Calculations for percentages
            'student_percentage': student_percentage,
            'staff_percentage': staff_percentage,
            'admin_percentage': admin_percentage,
        }
        
        return render(request, "analytics_dashboard.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading analytics: {str(e)}")
        return HttpResponseRedirect(reverse("admin_dashboard"))
    
@login_required(login_url='student_login')
def system_settings(request):
    """System settings page for admin"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    # System information
    total_users = User.objects.count()
    total_questions = QPattern.objects.count()
    total_subjects = Subject.objects.count()
    total_papers = StudentGeneratedPaper.objects.count()
    
    # Database information
    from django.db import connection
    db_info = {
        'engine': connection.vendor,
        'name': connection.settings_dict['NAME'],
        'version': connection.cursor().connection.server_version if connection.vendor == 'postgresql' else 'N/A'
    }
    
    context = {
        'total_users': total_users,
        'total_questions': total_questions,
        'total_subjects': total_subjects,
        'total_papers': total_papers,
        'db_info': db_info,
    }
    
    return render(request, "system_settings.html", context)
    

@login_required(login_url='student_login')
def explore_data(request):
    """Comprehensive data exploration page for admin"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    try:
        # Base querysets
        questions = QPattern.objects.select_related('subject', 'topic', 'user').all().order_by('-id')
        subjects = Subject.objects.all().order_by('name')
        all_users = User.objects.all().order_by('username')
        generated_papers = StudentGeneratedPaper.objects.select_related('student').all().order_by('-created_at')
        
        # Apply filters for questions
        search_query = request.GET.get('search', '')
        selected_subject = request.GET.get('subject', '')
        selected_marks = request.GET.get('marks', '')
        selected_difficulty = request.GET.get('difficulty', '')
        selected_user = request.GET.get('user', '')
        
        if search_query:
            questions = questions.filter(question__icontains=search_query)
        
        if selected_subject:
            questions = questions.filter(subject_id=selected_subject)
        
        if selected_marks:
            questions = questions.filter(marks=int(selected_marks))
        
        if selected_difficulty:
            questions = questions.filter(difficulty=int(selected_difficulty))
        
        if selected_user:
            questions = questions.filter(user_id=selected_user)
        
        # Statistics
        total_questions = QPattern.objects.count()
        total_subjects = Subject.objects.count()
        total_topics = Topic.objects.count()
        total_users = User.objects.count()
        total_generated_papers = StudentGeneratedPaper.objects.count()
        
        # Marks distribution
        marks_distribution = {
            'marks_2': QPattern.objects.filter(marks=2).count(),
            'marks_5': QPattern.objects.filter(marks=5).count(),
            'marks_10': QPattern.objects.filter(marks=10).count(),
            'total': QPattern.objects.aggregate(Sum('marks'))['marks__sum'] or 0
        }
        
        # Difficulty distribution
        difficulty_distribution = {}
        for i in range(1, 6):
            difficulty_distribution[f'level_{i}'] = QPattern.objects.filter(difficulty=i).count()
        
        # Get subjects with statistics using aggregation
        subjects_with_stats = []
        for subject in subjects:
            # Get question counts by marks for this subject
            marks_counts = QPattern.objects.filter(subject=subject).values('marks').annotate(count=Count('id'))
            
            marks_2_count = 0
            marks_5_count = 0
            marks_10_count = 0
            
            for item in marks_counts:
                if item['marks'] == 2:
                    marks_2_count = item['count']
                elif item['marks'] == 5:
                    marks_5_count = item['count']
                elif item['marks'] == 10:
                    marks_10_count = item['count']
            
            total_count = marks_2_count + marks_5_count + marks_10_count
            
            # Get topics for this subject
            subject_topics = []
            topics_for_subject = Topic.objects.filter(sub=subject)
            for topic in topics_for_subject:
                topic_count = QPattern.objects.filter(topic=topic).count()
                subject_topics.append({
                    'id': topic.id,
                    'name': topic.name,
                    'question_count': topic_count
                })
            
            # Calculate percentages safely
            marks_2_percent = (marks_2_count / total_count * 100) if total_count > 0 else 0
            marks_5_percent = (marks_5_count / total_count * 100) if total_count > 0 else 0
            marks_10_percent = (marks_10_count / total_count * 100) if total_count > 0 else 0
            
            subjects_with_stats.append({
                'id': subject.id,
                'name': subject.name,
                'question_count': total_count,
                'marks_2_count': marks_2_count,
                'marks_5_count': marks_5_count,
                'marks_10_count': marks_10_count,
                'marks_2_percent': marks_2_percent,
                'marks_5_percent': marks_5_percent,
                'marks_10_percent': marks_10_percent,
                'topics': subject_topics
            })
        
        # Pagination
        questions_per_page = 15
        papers_per_page = 10
        
        questions_paginator = Paginator(questions, questions_per_page)
        papers_paginator = Paginator(generated_papers, papers_per_page)
        
        page_questions = request.GET.get('page')
        page_papers = request.GET.get('page_papers')
        
        questions_page = questions_paginator.get_page(page_questions)
        papers_page = papers_paginator.get_page(page_papers)
        
        # Build query string for pagination
        query_params = request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        if 'page_papers' in query_params:
            del query_params['page_papers']
        query_string = query_params.urlencode()
        
        context = {
            # Data
            'questions': questions_page,
            'subjects': subjects,
            'all_users': all_users,
            'generated_papers': papers_page,
            'subjects_with_stats': subjects_with_stats,
            
            # Filters
            'search_query': search_query,
            'selected_subject': selected_subject,
            'selected_marks': selected_marks,
            'selected_difficulty': selected_difficulty,
            'selected_user': selected_user,
            'query_string': query_string,
            
            # Statistics
            'total_questions': total_questions,
            'total_subjects': total_subjects,
            'total_topics': total_topics,
            'total_users': total_users,
            'total_generated_papers': total_generated_papers,
            'marks_distribution': marks_distribution,
            'difficulty_distribution': difficulty_distribution,
        }
        
        # Handle exports
        export_format = request.GET.get('export')
        if export_format:
            return export_questions_data(questions, export_format)
        
        return render(request, "explore_data.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading data exploration: {str(e)}")
        return HttpResponseRedirect(reverse("admin_dashboard"))

def export_questions_data(queryset, format_type):
    """Export questions data in various formats"""
    try:
        if format_type == 'csv':
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="questions_export.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID', 'Question', 'Subject', 'Topic', 'Marks', 'Difficulty', 'Created By', 'User Role'])
            
            for question in queryset:
                writer.writerow([
                    question.id,
                    question.question,
                    question.subject.name,
                    question.topic.name,
                    question.marks,
                    question.difficulty,
                    question.user.username,
                    question.user.role
                ])
            
            return response
            
        elif format_type == 'json':
            from django.http import JsonResponse
            
            data = []
            for question in queryset:
                data.append({
                    'id': question.id,
                    'question': question.question,
                    'subject': question.subject.name,
                    'topic': question.topic.name,
                    'marks': question.marks,
                    'difficulty': question.difficulty,
                    'created_by': question.user.username,
                    'user_role': question.user.role
                })
            
            return JsonResponse(data, safe=False)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='student_login')
def question_detail_ajax(request, question_id):
    """AJAX view for question details"""
    try:
        question = get_object_or_404(QPattern, id=question_id)
        
        # Build the HTML content properly without Django template syntax
        html = f"""
        <div class="row">
            <div class="col-md-8">
                <h6>Question Text:</h6>
                <div class="border p-3 bg-light rounded mb-3">
                    {question.question}
                </div>
        """
        
        # Add answer section only if answer exists
        if question.answer:
            html += f"""
                <h6>Answer:</h6>
                <div class="border p-3 bg-light rounded">
                    {question.answer}
                </div>
            """
        
        # Continue with the rest of the HTML
        html += f"""
            </div>
            <div class="col-md-4">
                <h6>Details:</h6>
                <table class="table table-sm">
                    <tr><td><strong>Subject:</strong></td><td>{question.subject.name}</td></tr>
                    <tr><td><strong>Topic:</strong></td><td>{question.topic.name}</td></tr>
                    <tr><td><strong>Marks:</strong></td><td>{question.marks}</td></tr>
                    <tr><td><strong>Difficulty:</strong></td><td>{question.difficulty}/5</td></tr>
                    <tr><td><strong>Created By:</strong></td><td>{question.user.username} ({question.user.role})</td></tr>
                    <tr><td><strong>Created:</strong></td><td>{question.user.date_joined.strftime('%Y-%m-%d')}</td></tr>
                </table>
            </div>
        </div>
        """
        
        return JsonResponse({'success': True, 'html': html})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})@login_required(login_url='student_login')
def student_generate_custom_paper(request):
    """Generate a custom question paper for students from selected questions"""
    if request.method == "POST":
        try:
            selected_questions = request.POST.getlist('selected_questions')
            paper_title = request.POST.get('paper_title', 'Custom Practice Paper')
            
            if not selected_questions:
                messages.warning(request, "⚠️ Please select at least one question.")
                return HttpResponseRedirect(reverse("student_generate_custom_paper"))
            
            # Get the selected questions
            questions = QPattern.objects.filter(id__in=selected_questions)
            
            # Calculate total marks
            total_marks = sum(question.marks for question in questions)
            
            # Generate PDF
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # PDF header
            p.setFont("Times-Bold", 24)
            p.drawCentredString(width/2, height-50, paper_title.upper())
            p.setFont("Times-Roman", 16)
            p.drawCentredString(width/2, height-80, "Practice Question Paper")
            p.drawCentredString(width/2, height-105, f"Total Marks: {total_marks}")
            
            # Draw line
            p.line(50, height-120, width-50, height-120)
            
            # Instructions section
            y_position = height - 140
            p.setFont("Times-Bold", 14)
            p.drawString(50, y_position, "General Instructions:")
            y_position -= 25
            
            p.setFont("Times-Roman", 12)
            instructions = [
                "1. Answer all questions",
                "2. Show all working steps", 
                "3. Write neatly and legibly",
                "4. Calculators are allowed",
                "5. Time: 3 Hours",
            ]
            
            for instruction in instructions:
                p.drawString(60, y_position, instruction)
                y_position -= 15
            
            y_position -= 20
            
            # Questions section
            p.setFont("Times-Bold", 16)
            p.drawString(50, y_position, "QUESTIONS")
            y_position -= 30
            
            # Add questions to PDF
            question_number = 1
            for question in questions:
                if y_position < 100:  # New page if needed
                    p.showPage()
                    y_position = height - 50
                    p.setFont("Times-Roman", 12)
                
                # Question header
                p.setFont("Times-Bold", 12)
                p.drawString(50, y_position, f"Q{question_number}. [{question.marks} marks]")
                y_position -= 15
                
                p.setFont("Times-Roman", 10)
                p.drawString(50, y_position, f"Subject: {question.subject.name} | Topic: {question.topic.name}")
                y_position -= 20
                
                # Question text
                p.setFont("Times-Roman", 12)
                question_lines = simpleSplit(question.question, "Times-Roman", 12, width-100)
                for line in question_lines:
                    if y_position < 100:
                        p.showPage()
                        y_position = height - 50
                        p.setFont("Times-Roman", 12)
                    p.drawString(60, y_position, line)
                    y_position -= 15
                
                y_position -= 10  # Space between questions
                question_number += 1
            
            p.showPage()
            p.save()
            buffer.seek(0)
            
            # Save to student's generated papers history
            student_paper = StudentGeneratedPaper.objects.create(
                student=request.user,
                title=paper_title,
                total_marks=total_marks,
                number_of_questions=len(questions),
            )
            
            # Store the question IDs as JSON for reference
            question_ids = [q.id for q in questions]
            student_paper.set_question_ids(question_ids)
            student_paper.save()
            
            filename = f"Custom_Paper_{student_paper.id}.pdf"
            messages.success(request, "📄 Custom question paper generated successfully!")
            return FileResponse(buffer, as_attachment=True, filename=filename)
            
        except Exception as e:
            messages.error(request, f"❌ Error generating custom paper: {str(e)}")
            return HttpResponseRedirect(reverse("student_dashboard"))
    else:
        # GET request - show available questions for selection
        available_questions = QPattern.objects.all().order_by('subject__name', 'marks')
        subjects = Subject.objects.all()
        
        context = {
            'available_questions': available_questions,
            'subjects': subjects,
        }
        return render(request, "student_generate_paper.html", context)

@login_required(login_url='student_login')
def student_update_generated_paper(request, generated_paper_id):
    """Update a student's generated question paper"""
    try:
        generated_paper = StudentGeneratedPaper.objects.get(id=generated_paper_id, student=request.user)
        
        if request.method == "POST":
            selected_questions = request.POST.getlist('selected_questions')
            paper_title = request.POST.get('paper_title', generated_paper.title)
            
            if not selected_questions:
                messages.warning(request, "⚠️ Please select at least one question.")
                return HttpResponseRedirect(reverse("student_update_generated_paper", args=[generated_paper_id]))
            
            # Get the selected questions
            questions = QPattern.objects.filter(id__in=selected_questions)
            
            # Calculate total marks
            total_marks = sum(question.marks for question in questions)
            
            # Update the generated paper
            generated_paper.title = paper_title
            generated_paper.total_marks = total_marks
            generated_paper.number_of_questions = len(questions)
            generated_paper.set_question_ids([q.id for q in questions])
            generated_paper.save()
            
            # Generate updated PDF
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # PDF header
            p.setFont("Times-Bold", 24)
            p.drawCentredString(width/2, height-50, paper_title.upper())
            p.setFont("Times-Roman", 16)
            p.drawCentredString(width/2, height-80, "Practice Question Paper")
            p.drawCentredString(width/2, height-105, f"Total Marks: {total_marks}")
            
            # Draw line
            p.line(50, height-120, width-50, height-120)
            
            # Instructions section
            y_position = height - 140
            p.setFont("Times-Bold", 14)
            p.drawString(50, y_position, "General Instructions:")
            y_position -= 25
            
            p.setFont("Times-Roman", 12)
            instructions = [
                "1. Answer all questions",
                "2. Show all working steps", 
                "3. Write neatly and legibly",
                "4. Calculators are allowed",
                "5. Time: 3 Hours",
            ]
            
            for instruction in instructions:
                p.drawString(60, y_position, instruction)
                y_position -= 15
            
            y_position -= 20
            
            # Questions section
            p.setFont("Times-Bold", 16)
            p.drawString(50, y_position, "QUESTIONS")
            y_position -= 30
            
            # Add questions to PDF
            question_number = 1
            for question in questions:
                if y_position < 100:  # New page if needed
                    p.showPage()
                    y_position = height - 50
                    p.setFont("Times-Roman", 12)
                
                # Question header
                p.setFont("Times-Bold", 12)
                p.drawString(50, y_position, f"Q{question_number}. [{question.marks} marks]")
                y_position -= 15
                
                p.setFont("Times-Roman", 10)
                p.drawString(50, y_position, f"Subject: {question.subject.name} | Topic: {question.topic.name}")
                y_position -= 20
                
                # Question text
                p.setFont("Times-Roman", 12)
                question_lines = simpleSplit(question.question, "Times-Roman", 12, width-100)
                for line in question_lines:
                    if y_position < 100:
                        p.showPage()
                        y_position = height - 50
                        p.setFont("Times-Roman", 12)
                    p.drawString(60, y_position, line)
                    y_position -= 15
                
                y_position -= 10  # Space between questions
                question_number += 1
            
            p.showPage()
            p.save()
            buffer.seek(0)
            
            filename = f"Updated_Paper_{generated_paper.id}.pdf"
            messages.success(request, "🔄 Question paper updated successfully!")
            return FileResponse(buffer, as_attachment=True, filename=filename)
            
        else:
            # GET request - show form with current selection
            available_questions = QPattern.objects.all().order_by('subject__name', 'marks')
            current_question_ids = generated_paper.get_question_ids()
            subjects = Subject.objects.all()
            
            context = {
                'available_questions': available_questions,
                'current_question_ids': current_question_ids,
                'generated_paper': generated_paper,
                'subjects': subjects,
            }
            return render(request, "student_update_paper.html", context)
            
    except StudentGeneratedPaper.DoesNotExist:
        messages.error(request, "❌ Generated paper not found.")
        return HttpResponseRedirect(reverse("student_generated_papers"))
    except Exception as e:
        messages.error(request, f"❌ Error updating paper: {str(e)}")
        return HttpResponseRedirect(reverse("student_generated_papers"))

@login_required(login_url='student_login')
def student_delete_generated_paper(request, generated_paper_id):
    """Delete a student's generated question paper"""
    try:
        generated_paper = StudentGeneratedPaper.objects.get(id=generated_paper_id, student=request.user)
        paper_title = generated_paper.title
        generated_paper.delete()
        messages.success(request, f"🗑️ Question paper '{paper_title}' has been successfully deleted!")
        
    except StudentGeneratedPaper.DoesNotExist:
        messages.error(request, "❌ Generated paper not found.")
    
    return HttpResponseRedirect(reverse("student_generated_papers"))

@login_required(login_url='student_login')
def student_download_generated_paper(request, generated_paper_id):
    """Download a previously generated question paper"""
    try:
        generated_paper = StudentGeneratedPaper.objects.get(id=generated_paper_id, student=request.user)
        
        # Get the questions from stored IDs
        questions = generated_paper.get_questions()
        
        # Regenerate PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # PDF header
        p.setFont("Times-Bold", 24)
        p.drawCentredString(width/2, height-50, generated_paper.title.upper())
        p.setFont("Times-Roman", 16)
        p.drawCentredString(width/2, height-80, "Practice Question Paper")
        p.drawCentredString(width/2, height-105, f"Total Marks: {generated_paper.total_marks}")
        
        # Draw line
        p.line(50, height-120, width-50, height-120)
        
        # Instructions section
        y_position = height - 140
        p.setFont("Times-Bold", 14)
        p.drawString(50, y_position, "General Instructions:")
        y_position -= 25
        
        p.setFont("Times-Roman", 12)
        instructions = [
            "1. Answer all questions",
            "2. Show all working steps", 
            "3. Write neatly and legibly",
            "4. Calculators are allowed",
            "5. Time: 3 Hours",
        ]
        
        for instruction in instructions:
            p.drawString(60, y_position, instruction)
            y_position -= 15
        
        y_position -= 20
        
        # Questions section
        p.setFont("Times-Bold", 16)
        p.drawString(50, y_position, "QUESTIONS")
        y_position -= 30
        
        # Add questions to PDF
        question_number = 1
        for question in questions:
            if y_position < 100:  # New page if needed
                p.showPage()
                y_position = height - 50
                p.setFont("Times-Roman", 12)
            
            # Question header
            p.setFont("Times-Bold", 12)
            p.drawString(50, y_position, f"Q{question_number}. [{question.marks} marks]")
            y_position -= 15
            
            p.setFont("Times-Roman", 10)
            p.drawString(50, y_position, f"Subject: {question.subject.name} | Topic: {question.topic.name}")
            y_position -= 20
            
            # Question text
            p.setFont("Times-Roman", 12)
            question_lines = simpleSplit(question.question, "Times-Roman", 12, width-100)
            for line in question_lines:
                if y_position < 100:
                    p.showPage()
                    y_position = height - 50
                    p.setFont("Times-Roman", 12)
                p.drawString(60, y_position, line)
                y_position -= 15
            
            y_position -= 10  # Space between questions
            question_number += 1
        
        p.showPage()
        p.save()
        buffer.seek(0)
        
        filename = f"Generated_Paper_{generated_paper.id}.pdf"
        return FileResponse(buffer, as_attachment=True, filename=filename)
        
    except StudentGeneratedPaper.DoesNotExist:
        messages.error(request, "❌ Generated paper not found.")
        return HttpResponseRedirect(reverse("student_generated_papers"))
    except Exception as e:
        messages.error(request, f"❌ Error downloading generated paper: {str(e)}")
        return HttpResponseRedirect(reverse("student_generated_papers"))

@login_required(login_url='student_login')
def staff_generate_paper(request):
    """Staff-specific paper generation from question library"""
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, "Access denied. Staff privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    if request.method == "POST":
        try:
            selected_questions = request.POST.getlist('selected_questions')
            paper_title = request.POST.get('paper_title', 'Staff Generated Paper')
            instructions = request.POST.get('instructions', '')
            
            if not selected_questions:
                messages.warning(request, "⚠️ Please select at least one question.")
                return HttpResponseRedirect(reverse("staff_generate_paper"))
            
            # Get the selected questions
            questions = QPattern.objects.filter(id__in=selected_questions)
            
            # Calculate total marks and statistics
            total_marks = sum(question.marks for question in questions)
            difficulty_levels = [question.difficulty for question in questions]
            avg_difficulty = sum(difficulty_levels) / len(difficulty_levels) if difficulty_levels else 0
            
            # Generate PDF
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # PDF header
            p.setFont("Times-Bold", 24)
            p.drawCentredString(width/2, height-50, paper_title.upper())
            p.setFont("Times-Roman", 16)
            p.drawCentredString(width/2, height-80, "Staff Generated Question Paper")
            p.drawCentredString(width/2, height-105, f"Total Marks: {total_marks}")
            
            # Draw line
            p.line(50, height-120, width-50, height-120)
            
            # Paper statistics
            y_position = height - 140
            p.setFont("Times-Bold", 12)
            p.drawString(50, y_position, "Paper Statistics:")
            y_position -= 20
            
            p.setFont("Times-Roman", 10)
            stats = [
                f"Total Questions: {len(questions)}",
                f"Average Difficulty: {avg_difficulty:.1f}/5",
                f"Generated by: {request.user.username}",
                f"Date: {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            ]
            
            for stat in stats:
                p.drawString(60, y_position, stat)
                y_position -= 15
            
            y_position -= 10
            
            # Instructions section
            if instructions:
                p.setFont("Times-Bold", 12)
                p.drawString(50, y_position, "Instructions:")
                y_position -= 20
                
                p.setFont("Times-Roman", 10)
                instruction_lines = simpleSplit(instructions, "Times-Roman", 10, width-100)
                for line in instruction_lines:
                    if y_position < 100:
                        p.showPage()
                        y_position = height - 50
                        p.setFont("Times-Roman", 10)
                    p.drawString(60, y_position, line)
                    y_position -= 12
                
                y_position -= 10
            
            # General instructions
            p.setFont("Times-Bold", 12)
            p.drawString(50, y_position, "General Instructions:")
            y_position -= 20
            
            p.setFont("Times-Roman", 10)
            general_instructions = [
                "1. Answer all questions",
                "2. Show all working steps", 
                "3. Write neatly and legibly",
                "4. Calculators are allowed unless specified",
                "5. Time: As per examination guidelines",
            ]
            
            for instruction in general_instructions:
                if y_position < 100:
                    p.showPage()
                    y_position = height - 50
                    p.setFont("Times-Roman", 10)
                p.drawString(60, y_position, instruction)
                y_position -= 12
            
            y_position -= 20
            
            # Questions section
            p.setFont("Times-Bold", 16)
            p.drawString(50, y_position, "QUESTIONS")
            y_position -= 30
            
            # Add questions to PDF
            question_number = 1
            for question in questions:
                if y_position < 100:  # New page if needed
                    p.showPage()
                    y_position = height - 50
                    p.setFont("Times-Roman", 12)
                
                # Question header with marks and difficulty
                p.setFont("Times-Bold", 12)
                p.drawString(50, y_position, f"Q{question_number}. [{question.marks} marks]")
                p.setFont("Times-Roman", 10)
                p.drawString(width-150, y_position, f"Difficulty: {question.difficulty}/5")
                y_position -= 15
                
                # Subject and topic
                p.drawString(50, y_position, f"Subject: {question.subject.name} | Topic: {question.topic.name}")
                y_position -= 20
                
                # Question text
                p.setFont("Times-Roman", 12)
                question_lines = simpleSplit(question.question, "Times-Roman", 12, width-100)
                for line in question_lines:
                    if y_position < 100:
                        p.showPage()
                        y_position = height - 50
                        p.setFont("Times-Roman", 12)
                    p.drawString(60, y_position, line)
                    y_position -= 15
                
                # Answer space
                y_position -= 10
                if y_position < 150:
                    p.showPage()
                    y_position = height - 50
                p.line(50, y_position, width-50, y_position)
                y_position -= 20
                
                question_number += 1
            
            p.showPage()
            p.save()
            buffer.seek(0)
            
            filename = f"Staff_Generated_Paper_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
            messages.success(request, "📄 Question paper generated successfully!")
            return FileResponse(buffer, as_attachment=True, filename=filename)
            
        except Exception as e:
            messages.error(request, f"❌ Error generating paper: {str(e)}")
            return HttpResponseRedirect(reverse("staff_generate_paper"))
    else:
        # GET request - show available questions for selection
        if request.user.role == 'admin':
            available_questions = QPattern.objects.all().order_by('subject__name', 'marks')
        else:
            available_questions = QPattern.objects.filter(user=request.user).order_by('subject__name', 'marks')
        
        subjects = Subject.objects.all()
        
        context = {
            'available_questions': available_questions,
            'subjects': subjects,
        }
        return render(request, "staff_generate_paper.html", context)

def student_login(request):
    """Login page specifically for students"""
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role == 'student':
            login(request, user)
            messages.success(request, f"Welcome back, {username}! (Student)")
            return HttpResponseRedirect(reverse("student_dashboard"))
        else:
            return render(request, "student_login.html", {
                "message": "Invalid credentials or not a student account."
            })
    else:
        return render(request, "student_login.html")

def staff_login(request):
    """Login page specifically for staff"""
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role in ['staff', 'admin']:
            login(request, user)
            role_display = "Admin" if user.role == 'admin' else "Staff"
            messages.success(request, f"Welcome back, {username}! ({role_display})")
            return HttpResponseRedirect(reverse("staff_dashboard"))
        else:
            return render(request, "staff_login.html", {
                "message": "Invalid credentials or not a staff/admin account."
            })
    else:
        return render(request, "staff_login.html")

def admin_login(request):
    """Login page specifically for admin"""
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None and user.role == 'admin':
            login(request, user)
            messages.success(request, f"Welcome back, {username}! (Administrator)")
            return HttpResponseRedirect(reverse("admin_dashboard"))
        else:
            return render(request, "admin_login.html", {
                "message": "Invalid credentials or not an admin account."
            })
    else:
        return render(request, "admin_login.html")

def universal_login(request):
    """Universal login - redirects to appropriate dashboard"""
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            role_display = user.get_role_display()
            messages.success(request, f"Welcome back, {username}! ({role_display})")
            
            # Redirect based on role
            if user.role == 'admin':
                return HttpResponseRedirect(reverse("admin_dashboard"))
            elif user.role == 'staff':
                return HttpResponseRedirect(reverse("staff_dashboard"))
            else:
                return HttpResponseRedirect(reverse("student_dashboard"))
        else:
            return render(request, "universal_login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "universal_login.html")

def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        role = request.POST.get("role", "student")  # Default to student

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
            user.role = role
            user.save()
        except IntegrityError:
            return render(request, "register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        messages.success(request, f"Account created successfully! Welcome, {username}! ({user.get_role_display()})")
        return HttpResponseRedirect(reverse("dashboard"))
    else:
        return render(request, "register.html")
    
def student_register(request):
    """Student-specific registration page"""
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        
        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "student_register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new student user
        try:
            user = User.objects.create_user(username, email, password)
            user.role = 'student'  # Force student role
            user.save()
        except IntegrityError:
            return render(request, "student_register.html", {
                "message": "Username already taken."
            })
        
        login(request, user)
        messages.success(request, f"Account created successfully! Welcome, {username}! (Student)")
        return HttpResponseRedirect(reverse("student_dashboard"))
    else:
        return render(request, "student_register.html")

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    # Redirect to dashboard which shows all role options
    return HttpResponseRedirect(reverse("dashboard"))

@login_required(login_url='student_login')
def myquestions(request):
    """Question management - only for staff and admin"""
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, "Access denied. Staff privileges required to manage questions.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    if request.method == "POST":
        user = request.user
        subject_name = request.POST["subject"]
        topic_name = request.POST["topic"]
        marks = request.POST["marks"]
        difficulty = request.POST["difficulty"]
        question_text = request.POST["question"]
        answer = request.POST.get("answer", "")

        try:
            # Get or create subject
            subject_obj, subject_created = Subject.objects.get_or_create(name=subject_name)
            
            # Get or create topic
            topic_obj, topic_created = Topic.objects.get_or_create(
                name=topic_name,
                sub=subject_obj
            )
            
            # Create the question
            qamodel = QPattern.objects.create(
                user=user, 
                topic=topic_obj, 
                subject=subject_obj,
                question=question_text, 
                answer=answer, 
                marks=int(marks), 
                difficulty=int(difficulty)
            )
            
            messages.success(request, "✅ Question added successfully!")
            return HttpResponseRedirect(reverse("myquestions"))
            
        except Exception as e:
            messages.error(request, f"❌ Error adding question: {str(e)}")
            return HttpResponseRedirect(reverse("myquestions"))
            
    elif request.method == "GET":
        if request.user.role == 'admin':
            # Admin can see all questions
            questions = QPattern.objects.all().order_by('-id')
        else:
            # Staff can only see their own questions
            questions = QPattern.objects.filter(user=request.user).order_by('-id')
            
        return render(request, "myquestions.html", {
            "questions": questions,
        })
    else:
        return HttpResponseForbidden("Method not allowed")

@login_required(login_url='student_login')
def papergenerator(request):
    """Paper generation - only for staff and admin"""
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, "Access denied. Staff privileges required to generate papers.")
        return HttpResponseRedirect(reverse("dashboard"))
    
    return render(request, "index.html",{
        "subjects": Subject.objects.all()
    })

@login_required(login_url='student_login')
def papergen1(request):
    """Paper generation step 1 - only for staff and admin"""
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, "Access denied. Staff privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
        
    if request.method == "POST":
        checkboxstatus = False
        if request.POST.get('marksboxcheck', False) == 'on':
            checkboxstatus = True
        
        # Validate if there are enough questions for the selected paper type
        subsel = request.POST["subsel"]
        ptype = request.POST["ptype"]
        
        # Get the subject object
        subject = get_object_or_404(Subject, pk=subsel)
        topics = Topic.objects.filter(sub=subject)
        
        # Count available questions
        if request.user.role == 'admin':
            # Admin can use all questions
            total_questions = QPattern.objects.filter(subject_id=subsel).count()
            two_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=2).count()
            five_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=5).count()
            ten_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=10).count()
        else:
            # Staff can only use their own questions
            total_questions = QPattern.objects.filter(subject_id=subsel, user=request.user).count()
            two_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=2, user=request.user).count()
            five_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=5, user=request.user).count()
            ten_mark_questions = QPattern.objects.filter(subject_id=subsel, marks=10, user=request.user).count()
        
        # Validation messages
        if ptype == '1' and (two_mark_questions < 6 or five_mark_questions < 4):
            messages.warning(request, f"⚠️ Insufficient questions for IA Paper. Required: 6+ 2-mark questions (have {two_mark_questions}), 4+ 5-mark questions (have {five_mark_questions})")
        elif ptype == '2' and (five_mark_questions < 4 or ten_mark_questions < 10):
            messages.warning(request, f"⚠️ Insufficient questions for Semester Paper. Required: 4+ 5-mark questions (have {five_mark_questions}), 10+ 10-mark questions (have {ten_mark_questions})")
        else:
            messages.info(request, f"📊 Available: {two_mark_questions} 2-mark, {five_mark_questions} 5-mark, {ten_mark_questions} 10-mark questions")
        
        # Render index2.html with the context
        return render(request, "index2.html",{
            "heading": request.POST["heading"],
            "extradetails": request.POST.get("extradetails", ""),
            "marksboxcheck": checkboxstatus,
            "ptype": ptype,
            "subsel": subsel,
            "topics": topics
        })
    else:
        return HttpResponseForbidden("Method not allowed")

@login_required(login_url='student_login')
def papergen2(request):
    """Paper generation step 2 - only for staff and admin"""
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, "Access denied. Staff privileges required.")
        return HttpResponseRedirect(reverse("dashboard"))
        
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
        
        # Collect questions for selected topics based on user role
        for topic in topics:
            topic_obj = Topic.objects.filter(id=topic).first()
            if topic_obj:
                if request.user.role == 'admin':
                    # Admin can use all questions
                    twomqs.extend(list(QPattern.objects.filter(marks=2, topic=topic_obj)))
                    sevmqs.extend(list(QPattern.objects.filter(marks=5, topic=topic_obj)))
                    tens.extend(list(QPattern.objects.filter(marks=10, topic=topic_obj)))
                else:
                    # Staff can only use their own questions
                    twomqs.extend(list(QPattern.objects.filter(marks=2, topic=topic_obj, user=request.user)))
                    sevmqs.extend(list(QPattern.objects.filter(marks=5, topic=topic_obj, user=request.user)))
                    tens.extend(list(QPattern.objects.filter(marks=10, topic=topic_obj, user=request.user)))

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

@login_required(login_url='student_login')
def view_papers(request):
    """View available papers - accessible to all roles"""
    # Get all papers with related data
    papers = QPattern.objects.select_related('subject', 'topic', 'user').all().order_by('-id')
    
    # Apply filters if any
    subject_filter = request.GET.get('subject')
    if subject_filter:
        papers = papers.filter(subject__name__icontains=subject_filter)
    
    # Calculate statistics for the view
    total_papers = papers.count()
    total_questions = QPattern.objects.count()
    average_marks = QPattern.objects.aggregate(Avg('marks'))['marks__avg'] or 0
    
    # Since there's no created_at field, use total count for recent papers
    recent_papers = total_papers
    
    # Get marks distribution
    marks_distribution = {
        '2_marks': QPattern.objects.filter(marks=2).count(),
        '5_marks': QPattern.objects.filter(marks=5).count(),
        '10_marks': QPattern.objects.filter(marks=10).count(),
    }
    
    # Pagination
    paginator = Paginator(papers, 10)  # Show 10 papers per page
    page_number = request.GET.get('page')
    papers_page = paginator.get_page(page_number)
    
    context = {
        'papers': papers_page,
        'subjects': Subject.objects.all(),
        'total_papers': total_papers,
        'total_questions': total_questions,
        'average_marks': round(average_marks, 1),
        'recent_papers': recent_papers,
        'marks_distribution': marks_distribution,
    }
    
    return render(request, "view_papers.html", context)

@login_required(login_url='student_login')
def view_paper_detail(request, paper_id):
    """View detailed information about a specific paper"""
    paper = get_object_or_404(QPattern, id=paper_id)
    
    context = {
        'paper': paper,
    }
    
    return render(request, "view_paper_detail.html", context)

@login_required(login_url='student_login')
def download_paper_pdf(request, paper_id):
    """Download a specific paper as PDF - using existing student_download_paper functionality"""
    try:
        # Reuse the existing student_download_paper function
        return student_download_paper(request, paper_id)
    except Exception as e:
        messages.error(request, f"❌ Error downloading paper: {str(e)}")
        return HttpResponseRedirect(reverse("view_papers"))

@login_required(login_url='student_login')
def delete_paper(request, paper_id):
    """Delete a paper - only for staff and admin"""
    if request.user.role not in ['staff', 'admin']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Access denied. Staff privileges required.'})
        messages.error(request, "Access denied. Staff privileges required.")
        return HttpResponseRedirect(reverse("view_papers"))
    
    try:
        paper = get_object_or_404(QPattern, id=paper_id)
        
        # Check if user owns the paper or is admin
        if request.user.role != 'admin' and paper.user != request.user:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Access denied. You can only delete your own questions.'})
            messages.error(request, "Access denied. You can only delete your own questions.")
            return HttpResponseRedirect(reverse("view_papers"))
        
        paper_title = paper.question[:50] + "..." if len(paper.question) > 50 else paper.question
        paper.delete()
        
        # Return JSON response for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f"Question '{paper_title}' has been successfully deleted!"})
        
        messages.success(request, f"🗑️ Question '{paper_title}' has been successfully deleted!")
        
    except QPattern.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Question not found.'})
        messages.error(request, "❌ Question not found.")
    
    return HttpResponseRedirect(reverse("view_papers"))
