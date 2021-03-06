from datetime import datetime
from urllib.parse import urljoin
from flask import (
    request as flask_request,
    render_template,
    url_for
)
from flask_login import current_user
from app.response.utils import safely_send_and_add_email
from app.lib.db_utils import delete_object, create_object
from app.models import (
    Users,
    UserRequests,
    Requests,
    Events,
)
from app.lib.utils import UserRequestException
from app.lib.email_utils import get_agency_emails
from app.constants import event_type, permission, user_type_request


def add_user_request(request_id, user_guid, permissions):
    """
    Create a users permissions entry for a request and notify all agency administrators and the user that the permissions
    have changed.

    :param request_id: FOIL request ID
    :param user_guid: string guid of the user being edited
    :param permissions: Updated permissions values {'permission': true}
    """
    user_request = UserRequests.query.filter_by(user_guid=user_guid,
                                                request_id=request_id).first()

    agency_name = Requests.query.filter_by(id=request_id).one().agency.name

    if user_request:
        raise UserRequestException(action="create", request_id=request_id, reason="UserRequest entry already exists.")

    user = Users.query.filter_by(guid=user_guid).one()

    agency_admin_emails = get_agency_emails(request_id, admins_only=True)

    added_permissions = []
    for i, val in enumerate(permission.ALL):
        if i in permissions:
            added_permissions.append(val)

    # send email to agency administrators
    safely_send_and_add_email(
        request_id,
        render_template(
            'email_templates/email_user_request_added.html',
            request_id=request_id,
            name=user.name,
            agency_name=agency_name,
            page=urljoin(flask_request.host_url, url_for('request.view', request_id=request_id)),
            added_permissions=[capability.label for capability in added_permissions],
            admin=True),
        'User Added to Request {}'.format(request_id),
        to=agency_admin_emails)

    # send email to user being added
    safely_send_and_add_email(
        request_id,
        render_template(
            'email_templates/email_user_request_added.html',
            request_id=request_id,
            name=user.name,
            agency_name=agency_name,
            page=urljoin(flask_request.host_url, url_for('request.view', request_id=request_id)),
            added_permissions=[capability.label for capability in added_permissions],
        ),
        'User Added to Request {}'.format(request_id),
        to=[user.notification_email or user.email])

    user_request = UserRequests(
        user_guid=user.guid,
        auth_user_type=user.auth_user_type,
        request_id=request_id,
        request_user_type=user_type_request.AGENCY,
        permissions=0
    )

    create_object(user_request)

    if added_permissions:
        user_request.add_permissions([capability.value for capability in added_permissions])

    create_user_request_event(event_type.USER_ADDED, user_request)


def edit_user_request(request_id, user_guid, permissions):
    """
    Edit a users permissions on a request and notify all agency administrators and the user that the permissions
    have changed.

    :param request_id: FOIL request ID
    :param user_guid: string guid of the user being edited
    :param permissions: Updated permissions values {'permission': true}
    """
    user_request = UserRequests.query.filter_by(user_guid=user_guid,
                                                request_id=request_id).one()

    agency_admin_emails = get_agency_emails(request_id, admins_only=True)

    agency_name = Requests.query.filter_by(id=request_id).one().agency.name

    added_permissions = []
    removed_permissions = []
    for i, val in enumerate(permission.ALL):
        if i in permissions:
            added_permissions.append(val)
        else:
            removed_permissions.append(val)

    # send email to agency administrators
    safely_send_and_add_email(
        request_id,
        render_template(
            'email_templates/email_user_request_edited.html',
            request_id=request_id,
            name=user_request.user.name,
            agency_name=agency_name,
            page=urljoin(flask_request.host_url, url_for('request.view', request_id=request_id)),
            added_permissions=[capability.label for capability in added_permissions],
            removed_permissions=[capability.label for capability in removed_permissions],
            admin=True),
        'User Permissions Edited for Request {}'.format(request_id),
        to=agency_admin_emails)

    # send email to user being edited
    safely_send_and_add_email(
        request_id,
        render_template(
            'email_templates/email_user_request_edited.html',
            request_id=request_id,
            name=' '.join([user_request.user.first_name, user_request.user.last_name]),
            agency_name=agency_name,
            page=urljoin(flask_request.host_url, url_for('request.view', request_id=request_id)),
            added_permissions=[capability.label for capability in added_permissions],
            removed_permissions=[capability.label for capability in removed_permissions],
        ),
        'User Permissions Edited for Request {}'.format(request_id),
        to=[user_request.user.notification_email or user_request.user.email])

    old_permissions = user_request.permissions

    if added_permissions:
        user_request.add_permissions([capability.value for capability in added_permissions])
    if removed_permissions:
        user_request.remove_permissions([capability.value for capability in removed_permissions])

    create_user_request_event(event_type.USER_PERM_CHANGED, user_request, old_permissions)


def remove_user_request(request_id, user_guid):
    """
    Remove user from request and sends email to all agency administrators and to user being removed.
    Delete row from UserRequests table and stores event object into Events.

    :param request_id: FOIL request ID
    :param user_guid: string guid of user being removed

    """
    user_request = UserRequests.query.filter_by(user_guid=user_guid,
                                                request_id=request_id).first()
    agency_admin_emails = get_agency_emails(request_id, admins_only=True)

    agency_name = Requests.query.filter_by(id=request_id).one().agency.name

    # send email to agency administrators
    safely_send_and_add_email(
        request_id,
        render_template(
            'email_templates/email_user_request_removed.html',
            request_id=request_id,
            name=' '.join([user_request.user.first_name, user_request.user.last_name]),
            agency_name=agency_name,
            page=urljoin(flask_request.host_url, url_for('request.view', request_id=request_id)),
            admin=True),
        'User Removed from Request {}'.format(request_id),
        to=agency_admin_emails)

    # send email to user being removed
    safely_send_and_add_email(
        request_id,
        render_template(
            'email_templates/email_user_request_removed.html',
            request_id=request_id,
            name=' '.join([user_request.user.first_name, user_request.user.last_name]),
            agency_name=agency_name,
            page=urljoin(flask_request.host_url, url_for('request.view', request_id=request_id))),
        'User Removed from Request {}'.format(request_id),
        to=[user_request.user.email])

    create_user_request_event(event_type.USER_REMOVED, user_request)
    delete_object(user_request)


def create_user_request_event(events_type, user_request, old_permissions=None, user=current_user):
    """
    Create an Event for the addition, removal, or updating of a UserRequest

    """
    if old_permissions is not None:
        previous_value = {"permissions": old_permissions}
    else:
        previous_value = None
    create_object(Events(
        user_request.request_id,
        user.guid,
        user.auth_user_type,
        events_type,
        previous_value=previous_value,
        new_value=user_request.val_for_events,
        timestamp=datetime.utcnow(),
    ))
