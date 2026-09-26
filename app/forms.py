# -*- coding: utf-8 -*-
"""表单定义（共享，由甲统一维护）。

各模块的 Flask-WTF 表单集中于此。
"""
import re

from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, StringField, PasswordField, BooleanField
from wtforms.validators import (DataRequired, Length, Optional, EqualTo,
                                ValidationError)

from app.utils.constants import UNIT_TYPES, ASPECT_TYPES, GENDERS

# 邮箱格式：够用的轻量校验。
# WTForms 自带的 Email() 需要额外安装 email_validator，
# 为一个字段引入依赖不划算，这里自己用正则判断。
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def email_format(form, field):
    v = (field.data or "").strip()
    if v and not EMAIL_RE.match(v):
        raise ValidationError("邮箱格式不正确")


def email_ok(value):
    """邮箱格式判断，供不用 WTForms 的表单复用（如管理员编辑用户）。"""
    v = (value or "").strip()
    return (not v) or bool(EMAIL_RE.match(v))


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
    """登录表单。支持「记住我」以在关闭浏览器后保持登录状态。

    校验消息用中文写明：登录框带 novalidate，浏览器不会代填提示，
    字段为空时若不自己给消息，用户点了「登录」会以为没反应。
    """
    username = StringField("账户名称",
                           validators=[DataRequired(message="请输入账户名称"),
                                       Length(max=64,
                                              message="账户名称不能超过 64 个字符")])
    password = PasswordField("密码",
                             validators=[DataRequired(message="请输入密码")])
    remember = BooleanField("记住我")
    submit = SubmitField("登录")


GENDER_CHOICES = [("", "不填")] + [(g, g) for g in GENDERS]


class ProfileForm(FlaskForm):
    """个人资料：昵称、性别与联系方式。字段都可留空。

    职务不在这里 —— 只能由管理员在「个人设置 · 账号」里改。
    """
    display_name = StringField("昵称", validators=[Optional(), Length(max=64)])
    gender = SelectField("性别", choices=GENDER_CHOICES, validators=[Optional()])
    email = StringField("邮箱", validators=[Optional(), email_format,
                                        Length(max=128)])
    phone = StringField("手机号", validators=[Optional(), Length(max=32)])
    submit_info = SubmitField("保存资料")


class RegisterForm(FlaskForm):
    """注册：账号与密码必填，其余选填。注册后默认是操作员。"""
    username = StringField("账号名称",
                           validators=[DataRequired("请填写账号名称"),
                                       Length(min=2, max=64,
                                              message="账号名称 2–64 个字符")])
    password = PasswordField("密码",
                             validators=[DataRequired("请设置密码"),
                                         Length(min=6, max=64,
                                                message="密码至少 6 位")])
    confirm = PasswordField("确认密码",
                            validators=[DataRequired(),
                                        EqualTo("password",
                                                message="两次输入的密码不一致")])
    display_name = StringField("昵称", validators=[Optional(), Length(max=64)])
    gender = SelectField("性别", choices=GENDER_CHOICES, validators=[Optional()])
    email = StringField("邮箱", validators=[Optional(), email_format,
                                        Length(max=128)])
    phone = StringField("手机号", validators=[Optional(), Length(max=32)])
    submit_reg = SubmitField("注册并登录")


class PasswordForm(FlaskForm):
    """修改密码：需要先验证当前密码。"""
    old_password = PasswordField("当前密码", validators=[DataRequired()])
    new_password = PasswordField("新密码",
                                 validators=[DataRequired(), Length(min=6, max=64,
                                                                    message="新密码至少 6 位")])
    confirm = PasswordField("确认新密码",
                            validators=[DataRequired(),
                                        EqualTo("new_password",
                                                message="两次输入的新密码不一致")])
    submit_pwd = SubmitField("修改密码")
