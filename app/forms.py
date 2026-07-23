"""WTForms 폼 정의.

Flask-WTF 를 사용하면 폼마다 CSRF 토큰이 자동 포함/검증되고,
서버 측 입력 검증(길이/형식/범위)을 선언적으로 강제할 수 있다.
"""
import re

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, IntegerField, SelectField,
)
from wtforms.validators import (
    DataRequired, Length, Regexp, EqualTo, NumberRange, ValidationError,
)

USERNAME_RE = r"^[A-Za-z0-9_]+$"


class RegisterForm(FlaskForm):
    username = StringField("아이디", validators=[
        DataRequired(),
        Length(min=3, max=20, message="아이디는 3~20자여야 합니다."),
        Regexp(USERNAME_RE, message="아이디는 영문/숫자/밑줄만 사용할 수 있습니다."),
    ])
    password = PasswordField("비밀번호", validators=[
        DataRequired(),
        Length(min=8, max=128, message="비밀번호는 최소 8자 이상이어야 합니다."),
    ])
    confirm = PasswordField("비밀번호 확인", validators=[
        DataRequired(),
        EqualTo("password", message="비밀번호가 일치하지 않습니다."),
    ])

    def validate_password(self, field):
        pw = field.data
        # 최소한의 복잡도: 영문과 숫자를 각각 하나 이상 포함
        if not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
            raise ValidationError("비밀번호는 영문과 숫자를 모두 포함해야 합니다.")


class LoginForm(FlaskForm):
    username = StringField("아이디", validators=[DataRequired(), Length(max=20)])
    password = PasswordField("비밀번호", validators=[DataRequired(), Length(max=128)])


class ProfileForm(FlaskForm):
    bio = TextAreaField("소개글", validators=[Length(max=500)])


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField("현재 비밀번호", validators=[DataRequired()])
    new_password = PasswordField("새 비밀번호", validators=[
        DataRequired(),
        Length(min=8, max=128, message="비밀번호는 최소 8자 이상이어야 합니다."),
    ])
    confirm = PasswordField("새 비밀번호 확인", validators=[
        DataRequired(),
        EqualTo("new_password", message="비밀번호가 일치하지 않습니다."),
    ])


class ProductForm(FlaskForm):
    title = StringField("제목", validators=[
        DataRequired(), Length(min=1, max=100),
    ])
    description = TextAreaField("설명", validators=[
        DataRequired(), Length(min=1, max=2000),
    ])
    price = IntegerField("가격(원)", validators=[
        DataRequired(),
        NumberRange(min=0, max=1_000_000_000, message="가격 범위를 확인하세요."),
    ])
    # 이미지 파일은 라우트에서 별도 검증(save_uploaded_image)


class ReportForm(FlaskForm):
    reason = TextAreaField("신고 사유", validators=[
        DataRequired(), Length(min=5, max=500),
    ])


class PayoutAccountForm(FlaskForm):
    """판매자 정산 계좌. 계좌번호는 암호화해 저장한다."""
    bank_name = SelectField("은행", validators=[DataRequired()], choices=[
        ("", "은행을 선택하세요"),
        ("국민은행", "국민은행"), ("신한은행", "신한은행"), ("우리은행", "우리은행"),
        ("하나은행", "하나은행"), ("농협은행", "농협은행"), ("기업은행", "기업은행"),
        ("카카오뱅크", "카카오뱅크"), ("토스뱅크", "토스뱅크"), ("케이뱅크", "케이뱅크"),
        ("새마을금고", "새마을금고"), ("우체국", "우체국"),
    ])
    account_no = StringField("계좌번호", validators=[
        DataRequired(),
        Length(min=8, max=30),
        Regexp(r"^[0-9\-\s]+$", message="계좌번호는 숫자와 '-' 만 입력할 수 있습니다."),
    ])
    holder_name = StringField("예금주", validators=[
        DataRequired(), Length(min=2, max=30),
    ])


class TradeActionForm(FlaskForm):
    """거래 상태 전이용 (CSRF 토큰 전용 폼)."""
