import streamlit as st
import pandas as pd
import time
from google import genai
from apify_client import ApifyClient

st.set_page_config(page_title="AI 인플루언서 추출기 프로", layout="wide")
st.title("✨ AI 인플루언서 추출기 (실무 캠페인 최적화 버전)")
st.markdown("일반인 계정을 원천 차단하고, 2단계 프로필 검증을 통해 실무에 즉시 투입 가능한 규모감 있는 인플루언서만 엄선합니다.")

GEMINI_KEY = "AQ.Ab8RN6LCth3UNX4taroMZ1hqh57YFmYwWfkfw2Yi-R93FVgwbg"
APIFY_TOKEN = "apify_api_bjEdwAY1D8iyURBVYsSxAqaCBBxfsL0X9CQ4"

tab1, tab2 = st.tabs(["🚀 1단계: 규모별 인플루언서 발굴", "✉️ 2단계: 듀얼 섭외 메시지 생성"])

# ==========================================
# [탭 1] 실무형 2단계 정밀 인플루언서 추출기
# ==========================================
with tab1:
    with st.sidebar:
        st.header("🔍 캠페인 타겟팅 세팅")
        search_hashtag = st.text_input("메인 키워드 (# 제외)", value="야구직관")
        
        st.subheader("🎯 팔로워 규모 필터 (실무 필수)")
        # 최소 1,000명부터 시작하며, 기본값을 5,000명 이상으로 세팅해 일반인 계정을 원천 차단합니다.
        min_follower = st.number_input("최소 팔로워 수 (명 이상)", min_value=1000, max_value=1000000, value=5000, step=1000)
        max_follower = st.number_input("최대 팔로워 수 (명 이하)", min_value=1000, max_value=10000000, value=500000, step=5000)
        
        target_count = st.slider("최종 확보할 인플루언서 수 (명)", min_value=5, max_value=50, value=10, step=5,
                                  help="정밀 2단계 수집을 수행하므로 대량 수집 시 시간이 다소 소요됩니다.")
        
        brand_target = st.text_area("AI 판별 기준", value="야구(KBO)를 진심으로 좋아하고, 경기장 직관 콘텐츠를 올리며 팬들과 소통하는 인플루언서")
        run_btn = st.button("🚀 정밀 검증 추출 시작", use_container_width=True, type="primary")

    if run_btn:
        if not search_hashtag:
            st.error("메인 키워드를 입력해 주세요.")
        else:
            client = genai.Client(api_key=GEMINI_KEY)
            apify_client = ApifyClient(APIFY_TOKEN)
            
            # 1단계: 해시태그 기반 유저 후보군 수집
            with st.spinner("🧠 1/4 타겟 해시태그 및 연관 피드에서 유저 후보들을 1차 수집 중입니다..."):
                try:
                    tag_prompt = f"인스타그램 '{search_hashtag}' 연관 해시태그 3개 추천 (쉼표 구분, #제외)"
                    tag_response = client.models.generate_content(model='gemini-2.5-flash', contents=tag_prompt)
                    ai_hashtags = [tag.strip() for tag in tag_response.text.replace("#", "").split(",") if tag.strip()]
                    target_hashtags = [search_hashtag] + ai_hashtags[:2]
                    
                    # 후보군 확보를 위해 넉넉하게 스캔
                    run = apify_client.actor("apify/instagram-hashtag-scraper").call(
                        run_input={"hashtags": target_hashtags, "resultsLimit": target_count * 8}
                    )
                    dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
                    
                    raw_usernames = set()
                    user_captions = {}
                    user_likes = {}
                    
                    for item in apify_client.dataset(dataset_id).iterate_items():
                        username = item.get("ownerUsername")
                        if username and username != "unknown":
                            raw_usernames.add(username)
                            if username not in user_captions:
                                user_captions[username] = []
                                user_likes[username] = []
                            if item.get("caption"):
                                user_captions[username].append(item.get("caption"))
                            user_likes[username].append(item.get("likesCount", 0))
                except Exception as e:
                    st.error(f"1차 수집 중 오류: {e}")
                    st.stop()

            # 2단계: 추출된 유저들의 실제 프로필 정밀 2차 검증 (SaaS 핵심 로직)
            with st.spinner(f"🕵️ 2/4 일반인 계정 차단 중... {len(raw_usernames)}명의 실제 프로필 및 팔로워 수 정밀 검증 중..."):
                verified_user_map = {}
                try:
                    # 효율성을 위해 상위 후보군 리스트업하여 프로필 스크래퍼 실행
                    candidate_list = list(raw_usernames)[:target_count * 4]
                    profile_run = apify_client.actor("apify/instagram-profile-scraper").call(
                        run_input={"usernames": candidate_list}
                    )
                    profile_dataset_id = profile_run.get("defaultDatasetId") or profile_run.get("default_dataset_id")
                    
                    for p_item in apify_client.dataset(profile_dataset_id).iterate_items():
                        username = p_item.get("username")
                        followers = p_item.get("followersCount") or 0
                        following = p_item.get("followingCount") or 0
                        
                        # 💡 실무용 핵심 필터: 세팅된 팔로워 하한선 미만이거나 데이터 누락 계정은 가차없이 필터링
                        if not (min_follower <= followers <= max_follower):
                            continue
                            
                        # 맞팔로만 키운 스팸성 계정 방지 (팔로잉이 너무 과도하게 많은 일반인 차단)
                        if following > 4000 and followers < 5000:
                            continue
                            
                        verified_user_map[username] = {
                            "fullName": p_item.get("fullName", "이름 없음"),
                            "followers": followers,
                            "following": following,
                            "biography": p_item.get("biography", "계정 소개 없음"),
                            "likes": user_likes.get(username, [0]),
                            "captions": user_captions.get(username, ["정보 없음"])
                        }
                except Exception as e:
                    st.error(f"2차 프로필 검증 중 오류: {e}")
                    st.stop()

            # 3단계: 필터 통과한 알짜 인플루언서 AI 정밀 매칭 및 문맥 요약
            with st.spinner("🤖 3/4 캠페인 적합도 최종 분석 중... (무료 요금제용 속도 제어 가동)"):
                final_list = []
                if not verified_user_map:
                    st.warning(f"⚠️ 설정하신 최소 팔로워 {min_follower:,}명 기준을 충족하는 유저가 1차 후보군에 없습니다. 검색 키워드를 더 대중적인 단어로 바꾸거나 목표 인원을 조절해 주세요.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for username, info in verified_user_map.items():
                        if len(final_list) >= target_count:
                            break
                            
                        # 무료 API 429 에러 완화를 위한 필수 지연시간
                        time.sleep(4.2)
                        
                        avg_likes = sum(info["likes"][:9]) / len(info["likes"][:9]) if info["likes"] else 0
                        combined_caption = " / ".join(info["captions"])[:600]
                        profile_link = f"https://instagram.com/{username}"
                        
                        prompt = f'''
                        너는 13년 차 온라인 마케팅 전문가야. 아래 인플루언서가 우리 캠페인 기준에 맞는지 냉정하게 검증해줘.
                        [캠페인 기준]: {brand_target}
                        [유저 인포]: ID({username}), 소개글({info['biography']}), 최근 피드 문맥({combined_caption})
                        
                        반드시 아래 세 줄 양식만 출력해.
                        점수: [0~100 숫자]
                        추천: [YES 또는 NO]
                        요약: [이 인플루언서의 핵심 콘텐츠 특징과 카테고리 1줄 요약]
                        '''
                        
                        score, recommend, bio_summary = "확인불가", "NO", "내용 부족"
                        try:
                            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                            for line in response.text.strip().split('\n'):
                                if '점수:' in line: score = line.split(':', 1)[1].strip()
                                if '추천:' in line: recommend = line.split(':', 1)[1].strip()
                                if '요약:' in line: bio_summary = line.split(':', 1)[1].strip()
                        except Exception as e:
                            if "429" in str(e): bio_summary = "⏳ 한도 초과 (잠시 후 다시 시도)"
                            else: pass
                        
                        final_list.append({
                            "인스타그램 아이디": username,
                            "이름": info["fullName"],
                            "팔로워 수": f"{info['followers']:,}명",
                            "팔로잉 수": f"{info['following']:,}명",
                            "콘텐츠 특징 (AI 요약)": bio_summary,
                            "최근 피드 평균 좋아요": f"{round(avg_likes, 1):,}개",
                            "AI 점수": score,
                            "링크": profile_link
                        })
                        
                        current_progress = len(final_list) / target_count
                        progress_bar.progress(current_progress if current_progress <= 1.0 else 1.0)
                        status_text.text(f"🎯 실무형 인플루언서 검증 완료: {len(final_list)} / {target_count} 명")

                    df = pd.DataFrame(final_list)
                    status_text.empty()
                    st.success(f"🎉 실무 검증 완료! 설정하신 하한선({min_follower:,}명) 이상의 유효 인플루언서 명단입니다.")
                    st.dataframe(df, column_config={"링크": st.column_config.LinkColumn("인스타그램 링크")}, hide_index=True, use_container_width=True)
                    
                    csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                    st.download_button("📥 정밀 검증 명단 다운로드(CSV)", data=csv, file_name=f"실무인플루언서_{search_hashtag}.csv", mime="text/csv")

# ==========================================
# [탭 2] 듀얼 섭외 메시지 생성기 (유지)
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
            if not company_name or not influencer_name or not collab_details:
                st.warning("업체명, 협업 내용, 인플루언서 이름은 필수 항목입니다.")
            else:
                with st.spinner("AI가 각 잡힌 메시지와 친근한 메시지를 동시에 작성 중입니다..."):
                    try:
                        client = genai.Client(api_key=GEMINI_KEY)
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
