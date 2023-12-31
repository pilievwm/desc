"""empty message

Revision ID: 698e80ea9b50
Revises: 98b354a2a008
Create Date: 2023-09-07 11:47:38.101686

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '698e80ea9b50'
down_revision = '98b354a2a008'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('processed', schema=None) as batch_op:
        batch_op.add_column(sa.Column('published', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('published_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('processed_category', schema=None) as batch_op:
        batch_op.drop_column('published')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('processed_category', schema=None) as batch_op:
        batch_op.add_column(sa.Column('published', sa.BOOLEAN(), nullable=True))

    with op.batch_alter_table('processed', schema=None) as batch_op:
        batch_op.drop_column('published_at')
        batch_op.drop_column('published')

    # ### end Alembic commands ###
