# events.py
from sqlalchemy import event
from models import db, User, Ebook, Metadata, Logging
from datetime import datetime
from flask import session

def log_changes(mapper, connection, target):
    table_name = target.__tablename__
    action = "INSERT" if target in db.session.new else "UPDATE" if target in db.session.dirty else "DELETE"
    user_id = session.get('user_id')
    timestamp = datetime.utcnow()
    details = str(target)

    log_entry = Logging(
        table_name=table_name,
        action=action,
        user_id=user_id,
        timestamp=timestamp,
        details=details
    )
    db.session.add(log_entry)

# 이벤트 리스너 등록
event.listen(User, 'after_insert', log_changes)
event.listen(User, 'after_update', log_changes)
event.listen(User, 'after_delete', log_changes)

event.listen(Ebook, 'after_insert', log_changes)
event.listen(Ebook, 'after_update', log_changes)
event.listen(Ebook, 'after_delete', log_changes)

event.listen(Metadata, 'after_insert', log_changes)
event.listen(Metadata, 'after_update', log_changes)
event.listen(Metadata, 'after_delete', log_changes)