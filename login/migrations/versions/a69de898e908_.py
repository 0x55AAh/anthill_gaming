"""empty message

Revision ID: a69de898e908
Revises: c9b1c7eae0e7
Create Date: 2018-10-31 22:12:28.720416

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a69de898e908'
down_revision = 'c9b1c7eae0e7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('test', sa.String(length=128), nullable=False))
    op.create_unique_constraint(None, 'users', ['test'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_column('users', 'test')
    # ### end Alembic commands ###