import urllib.parse

from django.db import transaction
from django.shortcuts import (get_object_or_404,
                              redirect,
                              render)
from django.template.loader import get_template
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Notebook, NotebookRevision
from ..files.models import File
from ..base.models import User
from ..views import get_user_info_dict

from ..settings import (APP_VERSION_STRING,
                        EVAL_FRAME_ORIGIN)


def _get_user_info_json(user):
    if user.is_authenticated:
        return get_user_info_dict(user)
    return {}


def _get_iframe_src():
    return urllib.parse.urljoin(
        EVAL_FRAME_ORIGIN,
        'iodide.eval-frame.{}.html'.format(APP_VERSION_STRING)
    )


@ensure_csrf_cookie
def notebook_view(request, pk):
    notebook = get_object_or_404(Notebook, pk=pk)
    if 'revision' in request.GET:
        notebook_content = get_object_or_404(NotebookRevision, pk=int(request.GET['revision']))
    else:
        notebook_content = notebook.revisions.last()
    notebook_info = {
        'user_can_save': notebook.owner_id == request.user.id,
        'notebook_id': notebook.id,
        'revision_id': notebook_content.id,
        'connectionMode': 'SERVER',
        'title': notebook_content.title
    }
    if notebook.forked_from is not None:
        notebook_info['forked_from'] = notebook.forked_from.id
    else:
        notebook_info['forked_from'] = False
    return render(request, 'notebook.html', {
        'user_info': _get_user_info_json(request.user),
        'notebook_info': notebook_info,
        'jsmd': notebook_content.content,
        'iframe_src': _get_iframe_src()
    })


@ensure_csrf_cookie
def notebook_revisions(request, pk):
    pk = int(pk)
    nb = get_object_or_404(Notebook, pk=pk)
    owner = get_object_or_404(User, pk=nb.owner_id)
    owner_info = {
        'username': owner.username,
        'full_name': '{} {}'.format(owner.first_name, owner.last_name),
        'avatar': owner.avatar,
        'title': nb.title,
        'notebookId': nb.id,
    }
    if (nb.forked_from is not None):
        owner_info['forkedFromTitle'] = nb.forked_from.title
        owner_info['forkedFromRevisionID'] = nb.forked_from.id
        owner_info['forkedFromNotebookID'] = nb.forked_from.notebook_id
        owner_info['forkedFromUsername'] = nb.forked_from.notebook.owner.username

    files = [
        {'filename': file.filename,
         'id': file.id,
         'last_updated': file.last_updated.isoformat(sep=' '),
         'size': len(file.content)}
        for file in File.objects.filter(notebook_id=pk).order_by('-last_updated')
    ]
    revisions = list(reversed([{
        'id': revision.id,
        'notebookId': revision.notebook_id,
        'title': revision.title,
        'date': revision.created.isoformat(sep=' ')}
        for revision in NotebookRevision.objects.filter(notebook_id=pk)]))
    return render(request, '../templates/index.html', {
            'page_data': {
                'userInfo': get_user_info_dict(request.user),
                'ownerInfo': owner_info,
                'revisions': revisions,
                'files': files
            }
        }
    )


@ensure_csrf_cookie
def new_notebook_view(request):
    if not request.user.is_authenticated:
        return redirect(reverse('try-it'))

    # create a new notebook and redirect to its view
    new_notebook_content_template = get_template('new_notebook_content.jsmd')
    with transaction.atomic():
        notebook = Notebook.objects.create(owner=request.user)
        NotebookRevision.objects.create(
            notebook=notebook,
            content=new_notebook_content_template.render(),
            title='Untitled notebook'
        )
    return redirect(notebook)


@ensure_csrf_cookie
def tryit_view(request):
    '''
    A way to let new users experiment with iodide without logging in

    If user is logged in, redirect to `/new/`
    '''
    if request.user.is_authenticated:
        return redirect(new_notebook_view)
    # create a new notebook and redirect to its view
    new_notebook_content_template = get_template('new_notebook_content.jsmd')
    return render(request, 'notebook.html', {
        'user_info': {},
        'notebook_info': {
            'connectionMode': 'SERVER',
            'tryItMode': True,
            'title': 'Untitled notebook'
        },
        'jsmd': new_notebook_content_template.render(),
        'iframe_src': _get_iframe_src()
    })
