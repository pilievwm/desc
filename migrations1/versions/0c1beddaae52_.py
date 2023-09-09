"""empty message

Revision ID: 0c1beddaae52
Revises: a1b4b43744a4
Create Date: 2023-09-01 11:33:02.336885

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c1beddaae52'
down_revision = 'a1b4b43744a4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wiki_links', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.drop_column('wiki_links')

    # ### end Alembic commands ###
