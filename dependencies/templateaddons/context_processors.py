import re


def html_body_id(request):
    """
    Assign a variable name 'html_body_id' to the context.
    html_body_id value is computed from request.path.
    It corresponds to the first part of request.path.
    If request.path is '/', then 'home' is used as id. 
    """
    path_parts = request.path.split('/')
    i = 0
    while i < len(path_parts) and path_parts[i] == '':
        i += 1
    if i < len(path_parts):
        body_id = path_parts[i]
    else:
        body_id = 'home'
    
    return {
        'html_body_id': body_id
    }


def html_body_classes(request):
    """
    Assign a variable named 'html_body_classes' to the context.
    html_body_classes is a list of CSS classes suggestions computed from 
    request.path.
    
    Examples
    --------
    
    >>> from django.http import HttpRequest
    >>> my_request = HttpRequest()
    
    >>> my_request.path = '/'
    >>> html_body_classes(my_request)
    {'html_body_classes': ['fullpath--']}
    
    >>> my_request.path = '/one/two/three/'
    {'html_body_classes': ['fullpath--one--two--three', 'path--one', 'path--one--two']}
    
    >>> my_request.path = '/two-and-two/four/'
    {'html_body_classes': ['fullpath--two-and-two--four', 'path--two-and-two']}
    """
    classes = []
    
    path = request.path.strip('/')
    
    classes.append('fullpath--%s' % path.replace('/', '--'))
    
    if path:
        path_parts = path.split('/')
        current_path = 'path'
        for path_part in path_parts[0:-1]:
            current_path = '%s--%s' % (current_path, path_part)
            classes.append(current_path)
    
    return {
        'html_body_classes': classes
    }
