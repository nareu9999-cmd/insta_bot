import streamlit as st
import pandas as pd
import time
from google import genai
from apify_client import ApifyClient

st.set_page_config(page_title="AI 인플루언서 추출기 마스터", layout="wide")
st.title("✨ AI 인플루언서 추출기 (대량 추출 마스터 버전)")
st.markdown("AI가 연관 해시태그를 스스로 확장하여, 더 다양하고 퀄리티 높은 인플루언서를 대량으로 찾아냅니다.")

GEMINI_KEY = "AQ.Ab8RN6LCth3UNX4taroMZ1hqh57YFmYwWfkfw2Yi-R93FVgwbg"
APIFY_TOKEN = "apify_api_bjEdwAY1D8iyURBVYsSxAqaCBBxfsL0X9CQ4"

tab1, tab2 = st.tabs(["🚀 1단계: 조건별 인플루언서 발굴", "✉️ 2단계: 듀얼 섭외 메시지 생성"])

# ==========================================
# [탭 1] 인플루언서 추출 (AI 태그 확장 & 대량 스캔)
# ==========================================
with tab1:
    with st.sidebar:
        st.header("🔍 발굴 조건 세팅")
        search_hashtag = st.text_input("메인 키워드 (# 제외)", value="야구직관", help="입력하시면 AI가 연관 키워드를 자동으로 5개 더 확장하여 검색합니다.")
        
        st.subheader("🎯 수집 목표 및 필터링")
        # 💡 핵심 1: 목표 추출 인원 설정 (최대 100명)
        target_count = st.slider("목표 추출 인원 (명)", min_value=10, max_value=100, value=30, step=10, help="이 인원수가 채워질 때까지 AI가 계속 검색하고 분석합니다.")
        
        follower_range = st.slider("팔로워 수 범위 (명)", min_value=0, max_value=500000, value=(500, 100000), step=500)
        following_range = st.slider("팔로잉 수 범위 (명)", min_value=0, max_value=10000, value=(0, 5000), step=50)
        include_missing = st.checkbox("데이터 비공개 계정 포함하기", value=True)
        
        brand_target = st.text_area("AI 판별 기준", value="야구(KBO)를 진심으로 좋아하고, 경기장 직관 콘텐츠를 올리며 팬들과 소통하는 인플루언서")
        
        run_btn = st.button("🚀 AI 대량 추출 시작 (3~5분 소요)", use_container_width=True, type="primary")

    if run_btn:
        if not search_hashtag:
            st.error("메인 키워드를 입력해 주세요.")
        else:
            client = genai.Client(api_key=GEMINI_KEY)
            apify_client = ApifyClient(APIFY_TOKEN)
            
            # 1. AI 해시태그 자동 확장 로직
            with st.spinner("🧠 1/3 AI가 입력하신 키워드의 연관 트렌드 해시태그를 분석 중입니다..."):
                try:
                    tag_prompt = f"인스타그램에서 '{search_hashtag}'와 관련된 가장 인기 있고 퀄리티 높은 해시태그 5개를 추천해줘. 반드시 '#' 기호 없이 쉼표로만 구분해서 단어만 출력해. 예시: KBO,야구팬,최강야구,야구스타그램,직관러"
                    tag_response = client.models.generate_content(model='gemini-2.5-flash', contents=tag_prompt)
                    ai_hashtags = [tag.strip() for tag in tag_response.text.replace("#", "").split(",") if tag.strip()]
                    
                    target_hashtags = [search_hashtag] + ai_hashtags[:5] # 메인 키워드 + AI 추천 5개
                    st.info(f"💡 AI가 검색 풀을 넓혔습니다: {', '.join(target_hashtags)}")
                except:
                    target_hashtags = [search_hashtag, f"{search_hashtag}추천", f"{search_hashtag}그램"] # 실패 시 기본값
            
            # 2. Apify 대량 데이터 수집 (목표 인원의 5배수 스캔)
            with st.spinner(f"🕸️ 2/3 확장된 해시태그로 모수를 대량 수집 중입니다... (최대 {target_count * 5}개 게시물 스캔)"):
                try:
                    run = apify_client.actor("apify/instagram-hashtag-scraper").call(
                        run_input={"hashtags": target_hashtags, "resultsLimit": target_count * 5}
                    )
                    
                    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
                    if not dataset_id:
                        dataset_id = run.get("default_dataset_id") if isinstance(run, dict) else run.default_dataset_id

                    user_data_map = {}
                    for item in apify_client.dataset(dataset_id).iterate_items():
                        username = item.get("ownerUsername", "unknown")
                        if username == "unknown": continue
                            
                        followers = item.get("ownerFollowersCount") or 0
                        following = item.get("ownerFollowingCount") or 0
                        
                        if followers > 0:
                            if not (follower_range[0] <= followers <= follower_range[1]): continue
                        else:
                            if not include_missing: continue
                                
                        if following > 0:
                            if not (following_range[0] <= following <= following_range[1]): continue

                        if username not in user_data_map:
                            user_data_map[username] = {
                                "fullName": item.get("ownerFullName", "이름 없음"),
                                "followers": followers, "following": following,
                                "likes": [], "captions": []
                            }
                        user_data_map[username]["likes"].append(item.get("likesCount", -1))
                        
                        caption = item.get("caption", "")
                        if caption: user_data_map[username]["captions"].append(caption)
                except Exception as e:
                    st.error(f"데이터 수집 중 오류: {e}")
                    st.stop()

            # 3. 목표 인원 달성 시점까지 AI 정밀 분석
            with st.spinner("🤖 3/3 AI가 수집된 유저들을 검증하며 리스트를 작성 중입니다... (커피 한 잔 하고 오세요!)"):
                try:
                    final_list = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    if not user_data_map:
                        st.warning("⚠️ 필터 조건을 통과한 유저가 없습니다. 왼쪽 슬라이더 범위를 넓혀보세요!")
                    else:
                        for username, info in user_data_map.items():
                            # 💡 핵심 2: 목표 인원(100명 등)을 채우면 즉시 멈춤
                            if len(final_list) >= target_count:
                                break
                                
                            time.sleep(2) # 100명 대량 추출 시 AI 서버 과열 방지를 위한 필수 딜레이 (2초)
                            
                            valid_likes = [l for l in info["likes"] if l != -1 and l is not None]
                            avg_likes_str = f"{round(sum(valid_likes[:9]) / len(valid_likes[:9]), 1):,}개
