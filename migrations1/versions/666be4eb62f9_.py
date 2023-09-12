"""empty message

Revision ID: 666be4eb62f9
Revises: 0c1beddaae52
Create Date: 2023-09-01 12:46:18.008569

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '666be4eb62f9'
down_revision = '0c1beddaae52'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('include_intro', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('interesting_fact', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.drop_column('interesting_fact')
        batch_op.drop_column('include_intro')

    # ### end Alembic commands ###