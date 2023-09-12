"""empty message

Revision ID: a7b592db64c7
Revises: 63f6e756635d
Create Date: 2023-09-05 15:21:15.137413

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b592db64c7'
down_revision = '63f6e756635d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cat_links', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('category_settings', schema=None) as batch_op:
        batch_op.drop_column('cat_links')

    # ### end Alembic commands ###