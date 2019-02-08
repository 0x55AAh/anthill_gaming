# For more details, see
# http://docs.sqlalchemy.org/en/latest/orm/tutorial.html#declare-a-mapping
from anthill.framework.db import db
from anthill.framework.utils import timezone
from anthill.framework.utils.translation import translate as _
from anthill.framework.utils.asynchronous import as_future
from anthill.framework.utils.crypto import get_random_string
from anthill.framework.core.validators import RegexValidator
from sqlalchemy_utils.types.json import JSONType
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
import re


PROMO_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
PROMO_LENGTH = 12


promo_code_validator = RegexValidator(
    regex=r'^[A-Z0-9]{12}$', message=_('Promo code is not valid'))


def promo_code_cleaner(key):
    result = re.sub(r'[-\s]', '', key)
    result = result.upper()
    return result


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'

    key = db.Column(db.String(255), primary_key=True)
    count = db.Column(db.Integer, nullable=False, default=1)
    payload = db.Column(JSONType, nullable=False, default={})
    expires = db.Column(db.DateTime, nullable=False)

    async def save(self, *args, **kwargs):
        if not self.key:
            self.key = await self.generate_key()
        super().save(*args, **kwargs)

    @as_future
    def generate_key(self):
        return get_random_string(PROMO_LENGTH, PROMO_CHARS)

    @validates('key')
    def validate_key(self, key, value):
        value = promo_code_cleaner(value)
        promo_code_validator(value)
        return value

    @hybrid_property
    def expired(self):
        return self.expires <= timezone.now()

    @hybrid_property
    def available(self):
        return self.count > 0 and not self.expired

    async def use(self, commit=True):
        if not self.awailable:
            raise ValueError('Promo code is not available')
        self.count -= 1
        await self.save(commit=commit)
        return self.payload
