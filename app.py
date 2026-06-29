import streamlit as st
import pandas as pd
import time
from google import genai
from apify_client import ApifyClient

st.set_page_config(page_title="AI 인플루언서 추출기 프로", layout="wide")
st.title("✨ AI 인플루언서 추출기 (SaaS 플랫폼 버전)")
st.markdown("각 업체의 API 연동 키를 입력하여 비용 부담 없이 무제한으로 인플루언서를 발굴하고 검증하세요.")

tab1, tab2 = st.tabs(["🚀 1단계: 조건별 인플루언서 발굴", "✉️ 2단계: 듀얼 섭외 메시지 생성"])

# ==========================================
# [사이드바] 인증 정보 입력 및 친절한 가이드 추가
# ==========================================
with st.sidebar:
    st.header("🔑 API 인증 세팅")
    st.caption("이 서비스는 개별 API 키를 사용하므로 플랫폼 이용료가 발생하지 않습니다.")
    
    # 💡 업그레이드: 초보자도 쉽게 따라 할 수 있는 1분 발급 가이드 (접이식 메뉴)
    with st.expander("💡 1분만에 API 키 발급받는 방법 (클릭)", expanded=False):
        st.markdown("""
        **1. Google Gemini API 키 발급**
        * [Google AI Studio 접속](https://aistudio.google.com/) 후 로그인
        * 좌측 상단 **[Get API key]** 파란색 버튼 클릭
        * **[Create API key]** 누른 뒤 발급된 키(`AIzaSy...`) 복사!
        
        **2. Apify API 토큰 발급**
        * [Apify 가입 및 로그인](https://apify.com/)
        * 우측 상단 프로필 클릭 -> **[Settings]** 이동
        * 상단 메뉴 중 **[Integrations]** 탭 클릭
        * **API token** 항목 오른쪽에 있는 토큰 복사!
        
        ⚠️ *주의: 무료 크레딧 소진 시 결제 카드를 등록하셔야 대량 추출이 지속됩니다.*
        """)
        
    # 사용자 개인 키 입력창
    user_gemini_key = st.text_input("1. Google Gemini API Key 입력", type="password", help="구글 AI 스튜디오에서 발급받은 키를 입력하세요.")
    user_apify_token = st.text_input("2. Apify API Token 입력", type="password", help="Apify 계정 설정에서 발급받은 토큰을 입력하세요.")
    
    st.markdown("---")
    st.header("🔍 캠페인 타겟팅 세팅")
    search_mode = st.radio("검색 방식 선택", ["통합 키워드 검색 (계정명/프로필 기반)", "해시태그 검색 (# 기반)"])
    
    if search_mode == "해시태그 검색 (# 기반)":
        search_input = st.text_input("해시태그 입력 (# 제외)", value="야구직관")
    else:
        search_input = st.text_input("검색 키워드 입력", value="야구")
        
    st.subheader("🎯 팔로워 규모 필터")
    min_follower = st.number_input("최소 팔로워 수 (명 이상)", min_value=1000, value=5000, step=1000)
    max_follower = st.number_input("최대 팔로워 수 (명 이하)", min_value=1000, value=500000, step=5000)
    
    target_count = st.slider("최종 확보할 인플루언서 수 (명)", min_value=5, max_value=50, value=10, step=5)
    brand_target = st.text_area("AI 판별 기준", value="야구(KBO)를 진심으로 좋아하고, 경기장 직관 콘텐츠를 올리며 팬들과 소통하는 인플루언서")
    
    run_btn = st.button("🚀 정밀 추출 시작", use_container_width=True, type="primary")

# ==========================================
# [탭 1] 실무형 2단계 정밀 고도화 추출기 로직
# ==========================================
with tab1:
    if run_btn:
        if not user_gemini_key or not user_apify_token:
            st.error("🔒 사이드바 맨 위에 있는 'Gemini API Key'와 'Apify API Token'을 모두 입력하셔야 가동됩니다. 발급 방법을 참고해 주세요!")
        elif not search_input:
            st.error("검색어(태그/키워드)를 입력해 주세요.")
        else:
            try:
                client = genai.Client(api_key=user_gemini_key)
                apify_client = ApifyClient(user_apify_token)
            except Exception as init_err:
                st.error(f"입력하신 API 키 인증에 실패했습니다: {init_err}")
                st.stop()
                
            raw_usernames = set()
            user_captions = {}
            user_likes = {}
            
            # --- 1단계: 후보군 수집 ---
            if search_mode == "해시태그 검색 (# 기반)":
                with st.spinner("🧠 해시태그 피드에서 후보군을 수집 중입니다..."):
                    try:
                        tag_prompt = f"인스타그램 '{search_input}' 연관 해시태그 3개 추천 (쉼표 구분, #제외)"
                        tag_response = client.models.generate_content(model='gemini-2.5-flash', contents=tag_prompt)
                        ai_hashtags = [tag.strip() for tag in tag_response.text.replace("#", "").split(",") if tag.strip()]
                        target_hashtags = [search_input] + ai_hashtags[:2]
                        
                        run = apify_client.actor("apify/instagram-hashtag-scraper").call(
                            run_input={"hashtags": target_hashtags, "resultsLimit": target_count * 8}
                        )
                        dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
                        
                        for item in apify_client.dataset(dataset_id).iterate_items():
                            username = item.get("ownerUsername") or item.get("username")
                            if username and username != "unknown":
                                raw_usernames.add(username)
                                if username not in user_captions:
                                    user_captions[username] = []
                                    user_likes[username] = []
                                if item.get("caption"):
                                    user_captions[username].append(item.get("caption"))
                                if item.get("likesCount") is not None:
                                    user_likes[username].append(item.get("likesCount", 0))
                    except Exception as e:
                        st.error(f"❌ 수집 중 계정 한도 오류 발생: {e}\n입력하신 Apify 토큰 요금제의 제한을 확인해 주세요.")
                        st.stop()
            
            else:
                with st.spinner(f"🧠 통합 검색창에서 '{search_input}' 관련 유저 계정들을 수집 중입니다..."):
                    try:
                        run = apify_client.actor("apify/instagram-search-scraper").call(
                            run_input={
                                "searchQueries": [search_input],
                                "searchType": "user",
                                "resultsLimit": target_count * 6
                            }
                        )
                        dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
                        
                        for item in apify_client.dataset(dataset_id).iterate_items():
                            user_info = item.get("user")
                            username = user_info.get("username") if isinstance(user_info, dict) else item.get("username")
                            if username and username != "unknown":
                                raw_usernames.add(username)
                    except Exception as e:
                        st.error(f"❌ 수집 중 계정 한도 오류 발생: {e}\n입력하신 Apify 토큰 요금제의 제한을 확인해 주세요.")
                        st.stop()

            # --- 2단계: 프로필 정밀 검증 ---
            with st.spinner(f"🕵️ 일반인 계정 차단 중... {len(raw_usernames)}명의 프로필 유효성 검증 중..."):
                verified_user_map = {}
                try:
                    candidate_list = list(raw_usernames)[:target_count * 4]
                    if not candidate_list:
                        st.warning("⚠️ 탐색된 계정 후보가 없습니다. 검색 조건을 변경해 주세요.")
                        st.stop()
                        
                    profile_run = apify_client.actor("apify/instagram-profile-scraper").call(
                        run_input={"usernames": candidate_list}
                    )
                    profile_dataset_id = profile_run.get("defaultDatasetId") or profile_run.get("default_dataset_id")
                    
                    for p_item in apify_client.dataset(profile_dataset_id).iterate_items():
                        username = p_item.get("username")
                        if not username: continue
                        
                        followers = p_item.get("followersCount") or p_item.get("followers") or 0
                        following = p_item.get("followingCount") or p_item.get("following") or 0
                        
                        if not (min_follower <= followers <= max_follower): continue
                        if following > 4000 and followers < 5000: continue
                            
                        latest_posts = p_item.get("latestPosts", [])
                        likes = []
                        captions = []
                        
                        if isinstance(latest_posts, list):
                            for post in latest_posts:
                                if isinstance(post, dict):
                                    if post.get("likesCount") is not None: likes.append(post.get("likesCount", 0))
                                    if post.get("caption"): captions.append(post.get("caption"))
                        
                        p_likes = likes if likes else user_likes.get(username, [0])
                        p_captions = captions if captions else user_captions.get(username, ["정보 없음"])
                        
                        verified_user_map[username] = {
                            "fullName": p_item.get("fullName", "이름 없음"),
                            "followers": followers, "following": following,
                            "biography": p_item.get("biography", "계정 소개 없음"),
                            "likes": p_likes, "captions": p_captions
                        }
                except Exception as e:
                    st.error(f"2차 프로필 검증 오류: {e}")
                    st.stop()

            # --- 3단계: AI 매칭도 검증 및 바인딩 ---
            with st.spinner("🤖 캠페인 적합도 최종 분석 중..."):
                final_list = []
                if not verified_user_map:
                    st.warning("⚠️ 필터 조건을 충족하는 인플루언서가 후보군에 없습니다.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for username, info in verified_user_map.items():
                        if len(final_list) >= target_count: break
                        time.sleep(4.3)
                        
                        valid_likes = [l for l in info["likes"] if l is not None]
                        avg_likes = sum(valid_likes[:9]) / len(valid_likes[:9]) if valid_likes else 0
                        combined_caption = " / ".join(info["captions"])[:600]
                        profile_link = f"https://instagram.com/{username}"
                        
                        prompt = f'''
                        너는 마케팅 전문가야. 아래 인플루언서가 우리 캠페인 기준에 맞는지 검증해줘.
                        [캠페인 기준]: {brand_target}
                        [유저 인포]: ID({username}), 소개글({info['biography']}), 최근 피드 문맥({combined_caption})
                        
                        반드시 아래 세 줄 양식만 출력해.
                        점수: [0~100 숫자]
                        추천: [YES 또는 NO]
                        요약: [특징 1줄 요약]
                        '''
                        
                        score, recommend, bio_summary = "확인불가", "NO", "내용 부족"
                        try:
                            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                            for line in response.text.strip().split('\n'):
                                if '점수:' in line: score = line.split(':', 1)[1].strip()
                                if '추천:' in line: recommend = line.split(':', 1)[1].strip()
                                if '요약:' in line: bio_summary = line.split(':', 1)[1].strip()
                        except Exception as ai_err:
                            bio_summary = "⏳ AI 서버 과부하 또는 키 한도 초과"
                        
                        final_list.append({
                            "인스타그램 아이디": username, "이름": info["fullName"],
                            "팔로워 수": f"{info['followers']:,}명", "팔로잉 수": f"{info['following']:,}명",
                            "콘텐츠 특징 (AI 요약)": bio_summary, "최근 피드 평균 좋아요": f"{round(avg_likes, 1):,}개",
                            "AI 점수": score, "링크": profile_link
                        })
                        
                        current_progress = len(final_list) / target_count
                        progress_bar.progress(current_progress if current_progress <= 1.0 else 1.0)
                        status_text.text(f"🎯 정밀 발굴 완료: {len(final_list)} / {target_count} 명")

                    if final_list:
                        df = pd.DataFrame(final_list)
                        status_text.empty()
                        st.success("🎉 검증 완료!")
                        st.dataframe(df, column_config={"링크": st.column_config.LinkColumn("인스타그램 링크")}, hide_index=True, use_container_width=True)
                        csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                        st.download_button("📥 명단 다운로드(CSV)", data=csv, file_name=f"인플루언서추출_{search_input}.csv", mime="text/csv")

# ==========================================
# [탭 2] 듀얼 섭외 메시지 생성기
# ==========================================
with tab2:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.markdown("### 📝 제안서 정보 입력")
        company_name = st.text_input("업체(브랜드)명", placeholder="예: (주)투헬퍼스")
        manager_name = st.text_input("담당자 이름 및 직급", placeholder="예: 김철수 팀장")
        contact_info = st.text_input("회신 받을 연락처", placeholder="예: admin@example.com")
        collab_details = st.text_area("광고/협업 제안 내용", placeholder="예: 신제품 릴스 1회 업로드")
        product_url = st.text_input("상품 또는 브랜드 URL (선택)")
        st.markdown("---")
        influencer_name = st.text_input("타겟 인플루언서 ID 또는 이름")
        influencer_bio = st.text_area("인플루언서 계정 특징 (1단계 AI 요약 복사)")
        generate_btn = st.button("✨ 두 가지 버전 메시지 생성", use_container_width=True, type="primary")

    with col2:
        st.markdown("### 💌 AI 맞춤형 제안서 결과")
        if generate_btn:
            if not user_gemini_key:
                st.error("🔒 사이드바 맨 위에 있는 'Google Gemini API Key'를 먼저 입력하셔야 메시지가 생성됩니다.")
            elif not company_name or not influencer_name or not collab_details:
                st.warning("업체명, 협업 내용, 인플루언서 이름은 필수 항목입니다.")
            else:
                with st.spinner("AI가 제안서를 작성 중입니다..."):
                    try:
                        client = genai.Client(api_key=user_gemini_key)
                        prompt = f"""
                        너는 마케팅 전문가야. 아래 정보를 바탕으로 섭외 초안을 두 가지로 분리해서 작성해 줘.
                        - 브랜드명: {company_name} | 담당자: {manager_name} | 연락처: {contact_info}
                        - 제안내용: {collab_details} | URL: {product_url}
                        - 타겟: {influencer_name} | 특징: {influencer_bio}

                        출력 양식:
                        ## 💛 친근하고 부드러운 버전
                        [여기에 친근하고 텐션 높은 제안 문구 작성 (이모지 많이)]

                        ## 💼 정중한 비즈니스 버전
                        [여기에 프로페셔널한 제안 문구 작성 (이모지 자제)]
                        """
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        st.markdown(response.text)
                        st.success("✅ 생성 완료!")
                    except Exception as e:
                        st.error(f"오류 발생: {e}")
