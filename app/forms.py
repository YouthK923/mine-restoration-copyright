# -*- coding: utf-8 -*-
"""表单定义（共享，由甲统一维护）。

各模块的 Flask-WTF 表单集中于此。
"""
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length

from app.utils.constants import UNIT_TYPES, ASPECT_TYPES


class AHPSelectForm(FlaskForm):
    """选择微地质单元类型与指标层级，以确定判断矩阵规模。"""
    unit_type = SelectField("微地质单元类型", validators=[DataRequired()])
    level = SelectField("指标层级",
                        choices=[("1", "一级指标"), ("2", "二级指标")],
                        validators=[DataRequired()])
    l1 = SelectField("一级指标", validators=[], validate_choice=False)  # 动态填充，层级=2 时使用
    submit = SubmitField("生成判断矩阵")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unit_type.choices = [(t, t) for t in UNIT_TYPES]


class EmptyForm(FlaskForm):
    """仅用于承载 CSRF 令牌的空表单（矩阵录入等自定义表单使用）。"""
    pass


class LoginForm(FlaskForm):
    """登录表单。支持「记住我」以在关闭浏览器后保持登录状态。"""
    username = StringField("用户名", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("密码", validators=[DataRequired()])
    remember = BooleanField("记住我")
    submit = SubmitField("登录")
