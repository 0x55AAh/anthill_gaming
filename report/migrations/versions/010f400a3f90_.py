"""empty message

Revision ID: 010f400a3f90
Revises: 
Create Date: 2018-12-05 21:48:31.173231

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010f400a3f90'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('anthill_sessions',
    sa.Column('session_key', sa.String(length=40), nullable=False),
    sa.Column('session_data', sa.Text(), nullable=False),
    sa.Column('expire_date', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('session_key'),
    sa.UniqueConstraint('session_key')
    )
    op.create_index(op.f('ix_anthill_sessions_expire_date'), 'anthill_sessions', ['expire_date'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_anthill_sessions_expire_date'), table_name='anthill_sessions')
    op.drop_table('anthill_sessions')
    # ### end Alembic commands ###
