from django.shortcuts import render, redirect,get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed
from django.contrib.auth.decorators import login_required
from .models import Ticket,TicketStatus,Comment,Decision
from django.contrib.auth.models import AnonymousUser
from django.views.decorators.csrf import csrf_exempt
from userprofile.models import UserProfile,User
from django.core.paginator import Paginator
from django.http import HttpResponse
from .forms import TicketForm
from functools import wraps
import json
import datetime
import openpyxl

def add_profile_to_context(view_func):
    """
    Декоратор для добавления профиля пользователя в контекст представления.

    Этот декоратор автоматически получает профиль пользователя, используя текущего 
    пользователя (request.user), и добавляет его в объект запроса (`request.profile`). 
    Если профиль пользователя не найден, возвращается ошибка с кодом 400.

    Профиль пользователя будет доступен в любом представлении, использующем этот декоратор,
    что позволяет избежать повторного получения профиля в каждом представлении.

    Аргументы:
        view_func (function): Представление (функция), к которому применяется декоратор.
    
    Возвращаемое значение:
        function: Представление с добавленным профилем пользователя в объект запроса.

    Исключения:
        HttpResponse: Если профиль пользователя не найден, возвращается ошибка с кодом 400
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if isinstance(request.user, AnonymousUser):
            return redirect('/accounts/login/')  # Перенаправляем на страницу входа, если пользователь не авторизован.

        try:
            profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return HttpResponse("Профиль пользователя не найден.", status=400) 
        
        request.profile = profile  # Добавление профиля в объект запроса
        return view_func(request, *args, **kwargs)

    return _wrapped_view

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def index(request): 
    """
    Отображает главную страницу с данными о пользователе и статистикой тикетов.

    - Проверяет, существует ли профиль пользователя. Если нет — перенаправляет на страницу логина.
    - Подсчитывает общее количество тикетов, количество открытых и закрытых тикетов.
    - Передает данные в шаблон 'core/index.html'.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Сгенерированная HTML-страница с переданными в контексте данными.
    """
    try:
        request.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
 
    tickets_count = Ticket.objects.count()
    open_tickets_count = Ticket.objects.filter(status__id=1).count()
    closed_tickets_count = Ticket.objects.filter(status__id=4).count()
 
    context = {
        'user': request.user,
        'profile': request.profile,
        'tickets_count': tickets_count,
        'open_tickets_count': open_tickets_count,
        'closed_tickets_count': closed_tickets_count,
    }

    return render(request, 'core/index.html', context)

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def new_ticket(request): 
    tickets = Ticket.objects.all().order_by('-created_at')   
    tickets = tickets.filter(status__id__in=[1, 2,3])       
    search_field = request.GET.get("search_field")
    search_value = request.GET.get("search_value")

    if search_field and search_value: 
        if search_field == "client_name":
            tickets = tickets.filter(client_name__icontains=search_value)  
        elif search_field == "account_number":
            tickets = tickets.filter(account_number__icontains=search_value)
        elif search_field == "phone_number":
            tickets = tickets.filter(phone_number__icontains=search_value)

    paginator = Paginator(tickets, 6)
    page = request.GET.get('page')
    tickets = paginator.get_page(page)  
    return render(request, 'core/new_ticket.html', {
        'tickets': tickets,
        'search_field': search_field,
        'search_value': search_value, 
        'profile': request.profile,
        'search_query': f"&search_field={search_field}&search_value={search_value}" if search_field and search_value else ''
    })

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def add_ticket(request):
    """
    Отображает страницу списка тикетов с возможностью поиска и пагинации.

    - Получает профиль пользователя.
    - Загружает тикеты, отсортированные по дате создания, с фильтрацией по статусу (1, 2, 3).
    - Фильтрует тикеты по заданному полю (имя клиента, номер счета, номер телефона).
    - Реализует пагинацию (6 тикетов на страницу).
    - Передает данные в шаблон 'core/new_ticket.html'.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Сгенерированная HTML-страница с переданными в контексте данными.
    """
    profile = request.profile
    if request.user.is_superuser:
        assigned_to_queryset = User.objects.exclude(id=request.user.id)
        show_assigned_to_field = True
    elif profile.role == 'operator':
        assigned_to_queryset = User.objects.filter(userprofile__role='back_office')
        show_assigned_to_field = True
    else:
        assigned_to_queryset = User.objects.none()
        show_assigned_to_field = False

    if request.method == 'POST':
        form = TicketForm(request.POST)
        form.fields['assigned_to'].queryset = assigned_to_queryset

        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.status = TicketStatus.objects.get(id=1)
            ticket.created_by = request.user
            ticket.save()
            return redirect('new_ticket')  
    else:
        form = TicketForm()
        form.fields['assigned_to'].queryset = assigned_to_queryset
    context = {
        'form': form,
        'profile': request.profile,
        'show_assigned_to_field': show_assigned_to_field,
    }
    return render(request, 'core/add_ticket.html', context)

 
@login_required(login_url='/accounts/login/') 
def delete_ticket(request, ticket_id):
    """
    Удаляет тикет, если его статус — "Новая" (id = 1).

    - Проверяет, что запрос является POST.
    - Ищет тикет по переданному 'ticket_id', возвращает 404, если не найден.
    - Если статус тикета не "Новая", возвращает JSON-ответ с ошибкой.
    - В случае успеха удаляет тикет и возвращает JSON-ответ с подтверждением.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета, который нужно удалить.

    Returns:
        JsonResponse: Статус операции в формате JSON.
        HttpResponseNotAllowed: Ошибка при использовании метода, отличного от POST.
    """ 
    if request.method == 'POST':
        ticket = get_object_or_404(Ticket, id=ticket_id)
        if ticket.status.id == 1:
            ticket.delete()
        else:
            return JsonResponse({'status': 'error' , 'message': 'Вы не сможете удалить заявка которая статус не "Новая"'}) 
        return JsonResponse({'status': 'success'})
    else:
        return HttpResponseNotAllowed(['POST'])
    
@add_profile_to_context
@login_required(login_url='/accounts/login/')
def edit_ticket(request, ticket_id):
    """
    Редактирует тикет с учетом роли пользователя.

    - Получает тикет по 'ticket_id', возвращает 404, если не найден.
    - Определяет доступные для назначения пользователи в зависимости от роли:
      - Администратор: все пользователи, кроме текущего.
      - Оператор: только пользователи с ролью "back_office".
      - Остальные: поле назначения скрыто.
    - Если запрос POST, обновляет тикет и перенаправляет на страницу списка тикетов.
    - Если GET, загружает форму редактирования тикета.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета для редактирования.

    Returns:
        HttpResponse: Страница редактирования тикета.
        HttpResponseRedirect: Перенаправление на список тикетов после успешного сохранения.
    """
    ticket_edit = get_object_or_404(Ticket, id=ticket_id)
    profile = request.profile
    if request.user.is_superuser: 
        assigned_to_queryset = User.objects.exclude(id=request.user.id)  
        show_assigned_to_field = True
    elif profile.role == 'operator': 
        assigned_to_queryset = User.objects.filter(userprofile__role='back_office')
        show_assigned_to_field = True
    else: 
        assigned_to_queryset = User.objects.none()
        show_assigned_to_field = False
    if request.method == 'POST': 
        form = TicketForm(request.POST, instance=ticket_edit)
        form.fields['assigned_to'].queryset = assigned_to_queryset
        if form.is_valid():
            form.save()
            return redirect('new_ticket')  
    else: 
        form = TicketForm(instance=ticket_edit)
        form.fields['assigned_to'].queryset = assigned_to_queryset 
    context = {
        'form': form,
        'show_assigned_to_field': show_assigned_to_field,
        'profile': request.profile, 
        'ticket_edit': ticket_edit,
    } 
    return render(request, 'core/edit_ticket.html', context)

 
@login_required(login_url='/accounts/login/')
@csrf_exempt
def close_ticket(request, ticket_id):
    """
    Закрывает тикет, если его статус — "Решена" (id = 3).

    - Проверяет, что запрос является POST.
    - Ищет тикет по 'ticket_id', возвращает 404, если не найден.
    - Если статус тикета "Решена" и не "Выполнена", меняет его на "Выполнена" (id = 4).
    - Если статус "Выполнена" отсутствует в системе, возвращает сообщение об ошибке.
    - В случае успеха обновляет статус тикета и возвращает JSON-ответ.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета для закрытия.

    Returns:
        JsonResponse: Статус операции в формате JSON.
        HttpResponseNotAllowed: Ошибка при использовании метода, отличного от POST.
    """
    if request.method == 'POST': 
        ticket = get_object_or_404(Ticket, id=ticket_id) 
        if ticket.status.id == 3 and ticket.status and ticket.status.id != 4: 
            closed_status = TicketStatus.objects.filter(id=4).first()

            if closed_status: 
                ticket.status = closed_status
                ticket.save()
                return JsonResponse({'status': 'success', 'message': '✅ Тикет успешно закрыт. Статус изменен на "Закрыт".'})
            else:
                return JsonResponse({'status': 'error', 'message': '❌ Не удалось найти статус "Закрыт". Пожалуйста, убедитесь, что статус "Закрыт" существует в системе.'})
        else:
            return JsonResponse({'status': 'error', 'message': '⚠️ Если вы хотите закрыть задачу, ее статус должен быть "Решена".'})

    else:
        return HttpResponseNotAllowed(['POST'])

@add_profile_to_context   
@login_required(login_url='/accounts/login/')
def my_ticket(request):
    """
    Отображает список закрытых тикетов с возможностью поиска и пагинации.

    - Получает профиль пользователя.
    - Загружает тикеты, у которых статус "Выполнена" (id = 4), отсортированные по дате создания.
    - Фильтрует тикеты по заданному полю (имя клиента, номер счета, номер телефона).
    - Реализует пагинацию (6 тикетов на страницу).
    - Передает данные в шаблон 'core/my_ticket.html'.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Страница со списком закрытых тикетов.
    """ 
    tickets = Ticket.objects.all().order_by('-created_at')    
    tickets = tickets.filter(status__id__in=[4])       
    search_field = request.GET.get("search_field")
    search_value = request.GET.get("search_value")

    if search_field and search_value: 
        if search_field == "client_name":
            tickets = tickets.filter(client_name__icontains=search_value)  
        elif search_field == "account_number":
            tickets = tickets.filter(account_number__icontains=search_value)
        elif search_field == "phone_number":
            tickets = tickets.filter(phone_number__icontains=search_value)

    paginator = Paginator(tickets, 6)
    page = request.GET.get('page')
    tickets = paginator.get_page(page)  
    return render(request, 'core/my_ticket.html', {
        'tickets': tickets,
        'search_field': search_field,
        'search_value': search_value, 
        'profile': request.profile,
        'search_query': f"&search_field={search_field}&search_value={search_value}" if search_field and search_value else ''
    })

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def ticket_to_process(request):
    """
    Отображает список тикетов в процессе обработки с учетом роли пользователя.

    - Получает профиль пользователя.
    - Загружает тикеты со статусами "Новая", "Обработается" и "Решена" (id = 1, 2, 3), отсортированные по дате создания.
    - Фильтрует тикеты в зависимости от роли:
      - Администратор: видит все тикеты.
      - "Back Office": видит только тикеты, назначенные на него.
    - Позволяет фильтровать тикеты по имени клиента, номеру счета и номеру телефона.
    - Реализует пагинацию (6 тикетов на страницу).
    - Передает данные в шаблон 'core/ticket_to_process.html'.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Страница со списком тикетов в процессе обработки.
    """
    profile = request.profile
    tickets = Ticket.objects.all().order_by('-created_at')   
    tickets = tickets.filter(status__id__in=[1,2,3])

    if request.user.is_superuser: 
        tickets = tickets
    elif profile.role == 'back_office': 
        tickets = tickets.filter(assigned_to=request.user)  

    search_field = request.GET.get("search_field")
    search_value = request.GET.get("search_value")

    if search_field and search_value: 
        if search_field == "client_name":
            tickets = tickets.filter(client_name__icontains=search_value)  
        elif search_field == "account_number":
            tickets = tickets.filter(account_number__icontains=search_value)
        elif search_field == "phone_number":
            tickets = tickets.filter(phone_number__icontains=search_value)

    paginator = Paginator(tickets, 6)
    page = request.GET.get('page')
    tickets = paginator.get_page(page)  
    return render(request, 'core/ticket_to_process.html', {
        'tickets': tickets,
        'search_field': search_field,
        'search_value': search_value, 
        'profile': request.profile,
        'search_query': f"&search_field={search_field}&search_value={search_value}" if search_field and search_value else ''
    })

 
@login_required(login_url='/accounts/login/')
@csrf_exempt
def process_ticket(request, ticket_id):
    """
    Переводит тикет в статус "Обработается" (id = 2), если его текущий статус — "Новая" (id = 1).

    - Проверяет, что запрос является POST.
    - Ищет тикет по 'ticket_id', возвращает 404, если не найден.
    - Если статус тикета "Новая" и не "Обработается", изменяет его на "Обработается".
    - Если статус "Обработается" отсутствует в системе, возвращает сообщение об ошибке.
    - В случае успеха обновляет статус тикета и возвращает JSON-ответ.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета для обработки.

    Returns:
        JsonResponse: Статус операции в формате JSON.
        HttpResponseNotAllowed: Ошибка при использовании метода, отличного от POST.
    """
    if request.method == 'POST': 
        ticket = get_object_or_404(Ticket, id=ticket_id) 
        if ticket.status.id == 1 and ticket.status and ticket.status.id != 2: 
            process_status = TicketStatus.objects.filter(id=2).first()

            if process_status: 
                ticket.status = process_status
                ticket.save()
                return JsonResponse({'status': 'success', 'message': '✅ Тикет успешно обработан. Статус изменен на " В обработку".'})
            else:
                return JsonResponse({'status': 'error', 'message': '❌ Не удалось найти статус "В обработку". Пожалуйста, убедитесь, что статус "В обработку" существует в системе.'})
        else:
            return JsonResponse({'status': 'error', 'message': '⚠️ Если вы хотите обработать задачу, ее статус должен быть "Новая".'})

    else:
        return HttpResponseNotAllowed(['POST'])

 
@login_required(login_url='/accounts/login/')
def check_ticket_status(request, ticket_id):
    """
    Проверяет статус тикета. 

    - Получает тикет по 'ticket_id', возвращает 404, если не найден.
    - Если статус тикета "Обработается" (id = 2), возвращает JSON с success = True.
    - В противном случае возвращает JSON с success = False и сообщением об ошибке.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета для проверки.

    Returns:
        JsonResponse: JSON-ответ с результатом проверки статуса тикета.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
     
    if ticket.status.id == 2:
        return JsonResponse({'success': True})  
    else:
        return JsonResponse({'success': False, 'error': "⚠️ Если вы хотите решить задачу, ее статус должен быть 'Обработается'."})

@add_profile_to_context   
@login_required(login_url='/accounts/login/')
def complete_ticket(request, ticket_id):
    """
    Завершает обработку тикета, добавляя решение и изменяя его статус на "Решена" (id = 3).

    - Получает профиль пользователя и тикет по 'ticket_id', возвращает 404, если не найден.
    - Если метод запроса POST:
      - Парсит JSON-данные из тела запроса.
      - Проверяет, что поле "decision" не пустое.
      - Создает запись решения и обновляет статус тикета на "Решена".
      - Возвращает JSON-ответ об успешном обновлении.
    - Если метод GET, отображает страницу завершения тикета.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета для завершения.

    Returns:
        JsonResponse: При успешном обновлении или ошибке валидации.
        HttpResponse: Если метод GET — отображает страницу 'core/complete_ticket.html'.
    """ 
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method == 'POST': 
        try:
            data = json.loads(request.body)
            decision_content = data.get('decision', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'error': "Некорректные данные."}, status=400)

        if not decision_content:
            return JsonResponse({'error': "Решения  не может быть пустым."}, status=400) 
        Decision.objects.create(
            ticket=ticket,
            author=request.user,
            content=decision_content,
        )  
        ticket.status = TicketStatus.objects.get(id=3)  
        ticket.save()

        return JsonResponse({'success': "Заявка успешно обновлен."}) 
    
    return render(request, 'core/complete_ticket.html', {
        'ticket': ticket,
        'profile': request.profile
    })

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def back_office_rep(request):
    """
    Отображает тикеты с статусом "Выполнена" (id = 4), назначенные пользователю, с возможностью поиска и пагинации.

    - Получает профиль пользователя.
    - Загружает тикеты с статусом "Выполнена" (id = 4), назначенные пользователю, отсортированные по дате создания.
    - Позволяет фильтровать тикеты по имени клиента, номеру счета и номеру телефона.
    - Реализует пагинацию (6 тикетов на страницу).
    - Передает данные в шаблон 'core/back_office_rep.html'.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Страница со списком тикетов, назначенных пользователю.
    """ 
    tickets = Ticket.objects.filter(status__id=4, assigned_to=request.user).order_by('-created_at')   
    search_field = request.GET.get("search_field")
    search_value = request.GET.get("search_value") 
    if search_field and search_value:
        if search_field == "client_name":
            tickets = tickets.filter(client_name__icontains=search_value)
        elif search_field == "account_number":
            tickets = tickets.filter(account_number__icontains=search_value)
        elif search_field == "phone_number":
            tickets = tickets.filter(phone_number__icontains=search_value) 
    paginator = Paginator(tickets, 6)
    page = request.GET.get('page')
    tickets = paginator.get_page(page) 
    return render(request, 'core/back_office_rep.html', {
        'tickets': tickets,
        'search_field': search_field,
        'search_value': search_value,
        'profile': request.profile,
        'search_query': f"&search_field={search_field}&search_value={search_value}" if search_field and search_value else ''
    })

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def report_page(request):
    """
    Отображает страницу отчетов для пользователя.

    - Получает профиль пользователя.
    - Отображает страницу 'core/reports.html' с данными о профиле пользователя.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Страница отчетов с данными о пользователе.
    """ 
    return render(request, "core/reports.html", {'profile': request.profile})
 
@login_required(login_url='/accounts/login/')
def export_to_excel(request):
    """
    Экспортирует тикеты в Excel файл на основе выбранного диапазона дат.

    - Получает даты начала и окончания периода из GET-запроса.
    - Проверяет корректность формата дат.
    - Загружает профиль пользователя и фильтрует тикеты в зависимости от роли пользователя.
    - Генерирует Excel файл с данными тикетов, включая информацию о клиенте, статусе, исполнителе и других полях.
    - Отправляет файл Excel как ответ для скачивания.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Ответ с Excel файлом для скачивания.
    """
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if not start_date or not end_date:
        return HttpResponse("Пожалуйста, укажите обе даты.", status=400)
    try:
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse("Неверный формат даты.", status=400)
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return HttpResponse("Профиль пользователя не найден.", status=400)
    tickets = Ticket.objects.filter(created_at__date__range=(start_date, end_date))
    if profile.role == 'operator':
        tickets = tickets.filter(created_by=request.user) 
    elif profile.role == 'back_office':
        tickets = tickets.filter(assigned_to=request.user) 

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Заявки"

    headers = [
        "№", "ФИО", "Л/C", "Телефон", "Описание", 
        "Статус", "Исполнитель", "Создатель", "Дата создания", "Последнее обновление" 
    ]
    ws.append(headers)

    for ticket in tickets:
        ws.append([
            ticket.id,
            ticket.client_name,
            ticket.account_number,
            ticket.phone_number,
            ticket.description,
            ticket.status.name if ticket.status else "Не задано",
            ticket.assigned_to.username if ticket.assigned_to else "Не задано",
            ticket.created_by.username,
            ticket.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ticket.updated_at.strftime("%Y-%m-%d %H:%M:%S") 
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename=tickets_{start_date}_to_{end_date}.xlsx"
    wb.save(response)
    return response

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def about(request):
    """
    Отображает страницу с информацией о приложении для пользователя.

    - Получает профиль пользователя.
    - Отображает страницу 'core/about.html' с данными о профиле пользователя.

    Args:
        request (HttpRequest): Запрос от клиента.

    Returns:
        HttpResponse: Страница с информацией о приложении и данными о пользователе.
    """
     
    return render(request, "core/about.html", {'profile': request.profile})

@login_required(login_url='/accounts/login/')
def check_comment_ticket_status(request, ticket_id):
    """
    Проверяет, можно ли оставить комментарий для тикета на основе его статуса.

    - Получает тикет по 'ticket_id'.
    - Если статус тикета "Решена" (id = 3), возвращает JSON с успешным результатом.
    - Если статус тикета не "Решена", возвращает JSON с ошибкой и объяснением.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета для проверки.

    Returns:
        JsonResponse: Статус операции (успех или ошибка) в зависимости от статуса тикета.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
     
    if ticket.status.id == 3:
        return JsonResponse({'success': True})  
    else:
        return JsonResponse({'success': False, 'error': "⚠️ Если вы хотите оставить коментарию, ее статус должен быть 'Решена'."})
 
@add_profile_to_context
@login_required(login_url='/accounts/login/')
def comment_ticket(request, ticket_id):
    """
    Добавляет комментарий к тикету и изменяет его статус на "Обработается".

    - Получает тикет по 'ticket_id'.
    - Проверяет, что запрос использует метод POST и что данные в запросе корректны.
    - Добавляет комментарий к тикету и обновляет его статус на "Обработается".
    - Возвращает JSON ответ с успешным результатом или ошибкой.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета, к которому добавляется комментарий.

    Returns:
        JsonResponse: Ответ с информацией об успешном добавлении комментария или ошибке.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method == 'POST': 
        try:
            data = json.loads(request.body)
            comment_content = data.get('comments', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'error': "Некорректные данные."}, status=400)

        if not comment_content:
            return JsonResponse({'error': "Комментарий не может быть пустым."}, status=400)
 
        Comment.objects.create(
            ticket=ticket,
            author=request.user,
            content=comment_content,
        ) 
        ticket.status = TicketStatus.objects.get(id=2)
        ticket.save()

        return JsonResponse({'success': "Комментарий успешно добавлен."})  
     
    return render(request, 'core/comment_ticket.html', {
        'ticket': ticket,
        'profile': request.profile
    })

@add_profile_to_context
@login_required(login_url='/accounts/login/')
def ticket_details(request, ticket_id):
    """
    Отображает подробную информацию о тикете, включая комментарии и решения.

    - Получает тикет по 'ticket_id'.
    - Собирает все комментарии и решения, связанные с тикетом.
    - Объединяет комментарии и решения в общий таймлайн, сортируя их по времени создания.
    - Формирует таймлайн с типами элементов (комментарий или решение) для отображения.

    Args:
        request (HttpRequest): Запрос от клиента.
        ticket_id (int): ID тикета, для которого отображаются детали.

    Returns:
        HttpResponse: Рендерит шаблон с деталями тикета, таймлайном комментариев и решений.
    """ 
    ticket = get_object_or_404(Ticket, id=ticket_id)  
    comments = ticket.comments.all().order_by('created_at')   
    decisions = ticket.decisions.all().order_by('created_at') 
    timeline = list(comments) + list(decisions) 
    timeline = sorted(timeline, key=lambda x: x.created_at) 
    
    timeline_with_type = []

    for item in timeline:
        if isinstance(item, Comment):   
            timeline_with_type.append({'type': 'comment', 'object': item})
        elif isinstance(item, Decision):  
            timeline_with_type.append({'type': 'decision', 'object': item}) 
            
    return render(request, 'core/ticket_details.html', {
        'ticket': ticket,
        'timeline': timeline_with_type,
        'profile': request.profile,
    })