"""Presentation adapter for the user-approved Class 5 Social Chapter 1 look.

This changes only authored HTML/CSS, not narration, source text, media, or the
timing authority. Keep it opt-in until Chapter 2 encoded QA is approved.
"""

VARIANT = "class5-social-chapter1-v4"

CSS = """
    #educational-main { background-color:#DCEEF1; }
    .scene { background-color:transparent; padding:58px 62px 196px; }
    .scene.stable-teaching { background-color:#DCEEF1; }
    .scene.stable-teaching::before { display:none; }
    .scene.stable-teaching .native-visual { display:none; }
    .heading-hold { background:#DCEEF1; }
    .heading-hold h1 { background:#FFF9ED; padding:34px 48px; border-radius:26px;
        max-width:1450px; font-family:Nunito,"Segoe UI",Arial,sans-serif; font-size:66px;
        font-weight:800; box-shadow:0 12px 36px #12324714; }
    .heading-label { position:absolute; left:62px; top:58px; z-index:5; margin:0;
        max-width:1700px; padding:16px 28px; border-radius:14px;
        color:#A83C2D; background:#FFF9ED; font-family:Nunito,"Segoe UI",Arial,sans-serif;
        font-size:32px; line-height:1.25; font-weight:800; box-shadow:0 6px 22px #12324713; }
    .teaching-panel { top:140px; right:62px; width:610px; max-height:690px;
        padding:30px 34px; border:0; border-radius:26px; background:#FFF9ED;
        box-shadow:0 12px 38px #1232471a; }
    .teaching-panel .panel-body { margin:0; font-family:Georgia,serif;
        font-size:34px; line-height:1.42; }
    .teaching-panel .panel-body.text-medium { font-size:32px; }
    .teaching-panel .panel-body.text-long { font-size:29px; }
    .teaching-panel .panel-pages { margin-top:0; }
    .teaching-panel .panel-line { font-size:32px; line-height:1.4; }
    .source-figure { left:62px; top:177px; width:1040px; height:635px;
        padding:24px; border-radius:24px; background:#FFF9ED;
        box-shadow:0 12px 38px #1232471a; }
    .stable-teaching .teaching-panel { top:205px; left:245px; right:245px;
        width:auto; min-height:0; max-height:660px; padding:42px 48px;
        border:0; border-radius:26px; box-shadow:0 12px 36px #12324714; }
    .stable-teaching .teaching-panel .panel-body { font-size:38px; line-height:1.38; }
    .stable-teaching .teaching-panel .panel-body.text-medium { font-size:36px; }
    .stable-teaching .teaching-panel .panel-body.text-long { font-size:34px; }
    .stable-teaching .teaching-panel .panel-line { font-size:38px; }
    .opening-card { top:300px; left:100px; right:auto; width:800px; max-height:570px;
        padding:32px 40px; border:0; border-radius:26px; background:#FFF9ED;
        box-shadow:0 12px 40px #12324726; }
    .opening-card .panel-heading { color:#123247; font-family:Nunito,"Segoe UI",Arial,sans-serif;
        font-size:76px; line-height:1.07; letter-spacing:-1.5px; font-weight:800; }
    .opening-card .panel-body { color:#A83C2D; margin:0 0 12px;
        font-family:Nunito,"Segoe UI",Arial,sans-serif; font-size:30px;
        font-weight:800; letter-spacing:1px; }
    .opening-card .lesson-number { font-family:Nunito,"Segoe UI",Arial,sans-serif;
        font-size:27px; font-weight:700; margin:0 0 10px; }
    .subtitle-lane { left:150px; right:150px; bottom:44px; height:82px;
        border-radius:22px; padding:0 30px; background:#FFF9ED;
        box-shadow:0 6px 22px #12324713; }
    .caption-group { height:82px; font-family:Nunito,"Segoe UI",Arial,sans-serif;
        font-size:36px; font-weight:750; }
    .caption-word { padding:0 4px; border-radius:7px; }
    .v4-reading-list { display:flex; flex-direction:column; gap:13px; }
    .v4-reading-list .source-reading { margin:0; font-family:Georgia,serif;
        font-size:33px; line-height:1.38; padding:3px 8px; }
    .v4-reading-list .bullet-reading { padding-left:34px; position:relative; }
    .v4-reading-list .bullet-reading::before { content:"•"; position:absolute;
        left:4px; color:#A83C2D; }
    .v4-wordbank { width:100%; border-collapse:collapse; table-layout:fixed;
        font-family:Georgia,serif; font-size:31px; line-height:1.25; }
    .v4-wordbank th,.v4-wordbank td { padding:14px 18px; border-bottom:1px solid #12324725;
        text-align:left; vertical-align:top; }
    .v4-wordbank th { color:#A83C2D; background:#F4EBDC;
        font-family:Nunito,"Segoe UI",Arial,sans-serif; font-weight:800; }
    .v4-wordbank th:first-child,.v4-wordbank td:first-child { width:29%; }
"""
