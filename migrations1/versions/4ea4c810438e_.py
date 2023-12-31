"""empty message

Revision ID: 4ea4c810438e
Revises: 90875343a588
Create Date: 2023-08-31 12:02:29.005952

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4ea4c810438e'
down_revision = '90875343a588'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('processed_category', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token_count', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('processed_category', schema=None) as batch_op:
        batch_op.drop_column('token_count')

    # ### end Alembic commands ###
