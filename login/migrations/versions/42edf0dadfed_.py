"""empty message

Revision ID: 42edf0dadfed
Revises: 
Create Date: 2018-11-19 22:36:37.439753

"""
from alembic import op
import sqlalchemy as sa
import social_sqlalchemy


# revision identifiers, used by Alembic.
revision = '42edf0dadfed'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('abilities',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('anthill_sessions',
    sa.Column('session_key', sa.String(length=40), nullable=False),
    sa.Column('session_data', sa.Text(), nullable=False),
    sa.Column('expire_date', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('session_key'),
    sa.UniqueConstraint('session_key')
    )
    op.create_index(op.f('ix_anthill_sessions_expire_date'), 'anthill_sessions', ['expire_date'], unique=False)
    op.create_table('roles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('social_auth_association',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_url', sa.String(length=255), nullable=True),
    sa.Column('handle', sa.String(length=255), nullable=True),
    sa.Column('secret', sa.String(length=255), nullable=True),
    sa.Column('issued', sa.Integer(), nullable=True),
    sa.Column('lifetime', sa.Integer(), nullable=True),
    sa.Column('assoc_type', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('server_url', 'handle')
    )
    op.create_table('social_auth_code',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('code', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', 'email')
    )
    op.create_index(op.f('ix_social_auth_code_code'), 'social_auth_code', ['code'], unique=False)
    op.create_table('social_auth_nonce',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_url', sa.String(length=255), nullable=True),
    sa.Column('timestamp', sa.Integer(), nullable=True),
    sa.Column('salt', sa.String(length=40), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('server_url', 'timestamp', 'salt')
    )
    op.create_table('social_auth_partial',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(length=32), nullable=True),
    sa.Column('data', social_sqlalchemy.storage.JSONType(), nullable=True),
    sa.Column('next_step', sa.Integer(), nullable=True),
    sa.Column('backend', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_social_auth_partial_token'), 'social_auth_partial', ['token'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('password', sa.String(), nullable=True),
    sa.Column('username', sa.String(length=128), nullable=False),
    sa.Column('email', sa.String(length=128), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('role_ability',
    sa.Column('role_id', sa.Integer(), nullable=True),
    sa.Column('ability_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['ability_id'], ['abilities.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], )
    )
    op.create_table('social_auth_usersocialauth',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=True),
    sa.Column('uid', sa.String(length=255), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('extra_data', social_sqlalchemy.storage.JSONType(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'uid')
    )
    op.create_index(op.f('ix_social_auth_usersocialauth_user_id'), 'social_auth_usersocialauth', ['user_id'], unique=False)
    op.create_table('user_role',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('role_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user_role')
    op.drop_index(op.f('ix_social_auth_usersocialauth_user_id'), table_name='social_auth_usersocialauth')
    op.drop_table('social_auth_usersocialauth')
    op.drop_table('role_ability')
    op.drop_table('users')
    op.drop_index(op.f('ix_social_auth_partial_token'), table_name='social_auth_partial')
    op.drop_table('social_auth_partial')
    op.drop_table('social_auth_nonce')
    op.drop_index(op.f('ix_social_auth_code_code'), table_name='social_auth_code')
    op.drop_table('social_auth_code')
    op.drop_table('social_auth_association')
    op.drop_table('roles')
    op.drop_index(op.f('ix_anthill_sessions_expire_date'), table_name='anthill_sessions')
    op.drop_table('anthill_sessions')
    op.drop_table('abilities')
    # ### end Alembic commands ###