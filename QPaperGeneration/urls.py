from django.urls import path 
from . import views 
 
urlpatterns = [           
    # Main dashboard and authentication
    path("", views.dashboard, name="dashboard"),   
    path("index", views.index, name="index"),     
        
    # Separate Login Pages  
    path("student-login", views.student_login, name="student_login"),  
    path("staff-login", views.staff_login, name="staff_login"),
    path("admin-login", views.admin_login, name="admin_login"),
    path("universal-login", views.universal_login, name="universal_login"),  
    
    # Universal logout
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path('student-register/', views.student_register, name='student_register'),
    
    # Role-specific dashboards
    path("admin-dashboard", views.admin_dashboard, name="admin_dashboard"),
    path("staff-dashboard", views.staff_dashboard, name="staff_dashboard"),
    path("student-dashboard", views.student_dashboard, name="student_dashboard"),
    
    # Question management
    path("myquestions", views.myquestions, name="myquestions"),
    path("papergenerator", views.papergenerator, name="papergenerator"),
    path("papergen1", views.papergen1, name="papergen1"),
    path("papergen2", views.papergen2, name="papergen2"),
    path("view-papers", views.view_papers, name="view_papers"),
    
    # Student paper management
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student-download-paper/<int:paper_id>/', views.student_download_paper, name='student_download_paper'),
    path('student-generate-paper/', views.student_generate_custom_paper, name='student_generate_custom_paper'),
    path('student-generated-papers/', views.student_generated_papers, name='student_generated_papers'),
    path('staff-generate-paper/', views.staff_generate_paper, name='staff_generate_paper'),
    path('student-download-generated-paper/<int:generated_paper_id>/', views.student_download_generated_paper, name='student_download_generated_paper'),
    path('student-update-generated-paper/<int:generated_paper_id>/', views.student_update_generated_paper, name='student_update_generated_paper'),
    path('student-delete-generated-paper/<int:generated_paper_id>/', views.student_delete_generated_paper, name='student_delete_generated_paper'),
    
    # View papers and related URLs (NEWLY ADDED)
    path('paper/<int:paper_id>/', views.view_paper_detail, name='view_paper_detail'),
    path('paper/<int:paper_id>/download/', views.download_paper_pdf, name='download_paper_pdf'),
    path('paper/<int:paper_id>/delete/', views.delete_paper, name='delete_paper'),
    path('paper/<int:paper_id>/delete/', views.delete_paper, name='delete_paper'),
    
    
    path('user-management/', views.user_management, name='user_management'),
    path('user-management/create/', views.create_user, name='create_user'),
    path('user-management/update/<int:user_id>/', views.update_user, name='update_user'),
    path('user-management/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('user-management/reset-password/<int:user_id>/', views.reset_user_password, name='reset_user_password'),
    
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('system-settings/', views.system_settings, name='system_settings'),
    path('explore-data/', views.explore_data, name='explore_data'),
    path('question/<int:question_id>/detail/', views.question_detail_ajax, name='question_detail_ajax'),
    
]
