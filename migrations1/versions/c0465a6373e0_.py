"""empty message

Revision ID: c0465a6373e0
Revises: 4ea4c810438e
Create Date: 2023-08-31 21:21:42.366247

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c0465a6373e0'
down_revision = '4ea4c810438e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.drop_column('category_links')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_links', sa.INTEGER(), nullable=True))

    # ### end Alembic commands ###
