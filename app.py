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
                            avg_likes_str = f"{round(sum(valid_likes[:9]) / len(valid_likes[:9]), 1):,}개" if valid_likes else "숨김"
                            
                            follower_display = f"{info['followers']:,}명" if info['followers'] > 0 else "수집 불가(비공개)"
                            following_display = f"{info['following']:,}명" if info['following'] > 0 else "수집 불가(비공개)"
                            combined_caption = " / ".join(info["captions"])[:800] 
                            profile_link = f"https://instagram.com/{username}"
                            
                            prompt = f'''
                            마케팅 전문가로서 아래 유저가 타겟 기준에 맞는지 판별해.
                            [타겟 기준]: {brand_target}
                            [유저 정보]: ID({username}), 최근글({combined_caption})
                            
                            반드시 아래 세 줄 양식만 출력해.
                            점수: [0~100 숫자]
                            추천: [YES 또는 NO]
                            요약: [특징 1~2줄]
                            '''
                            
                            score, recommend, bio_summary = "확인불가", "NO", "내용 부족"
                            try:
                                response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                                for line in response.text.strip().split('\n'):
                                    if '점수:' in line: score = line.split(':', 1)[1].strip()
                                    if '추천:' in line: recommend = line.split(':', 1)[1].strip()
                                    if '요약:' in line: bio_summary = line.split(':', 1)[1].strip()
                            except Exception as e:
                                if "429" in str(e): bio_summary = "⏳ 한도 초과 대기 중"
                                else: pass
                            
                            # 추천이 YES이거나 의미 있는 점수가 나온 계정만 엄선해서 담기 (옵션)
                            final_list.append({
                                "인스타그램 아이디": username, "이름": info["fullName"],
                                "팔로워 수": follower_display, "팔로잉 수": following_display,
                                "계정 설명 (AI 요약)": bio_summary, "최근 9개 평균 좋아요": avg_likes_str,
                                "AI 점수": score, "링크": profile_link
                            })
                            
                            # 퍼센트 바 업데이트
                            current_progress = len(final_list) / target_count
                            progress_bar.progress(current_progress if current_progress <= 1.0 else 1.0)
                            status_text.text(f"🔍 현재 {len(final_list)} / {target_count} 명 발굴 완료!")

                        df = pd.DataFrame(final_list)
                        status_text.empty()
                        st.success(f"🎉 목표 인원에 도달했습니다! 총 {len(df)}명의 고품질 인플루언서 발굴 완료.")
                        st.dataframe(df, column_config={"링크": st.column_config.LinkColumn("인스타그램 링크")}, hide_index=True, use_container_width=True)
                        
                        csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                        st.download_button("📥 발굴 완료 명단 다운로드", data=csv, file_name=f"대량추출_{search_hashtag}.csv", mime="text/csv")
                        
                except Exception as e:
                    st.error(f"오류 발생: {e}")

# ==========================================
# [탭 2] 듀얼 섭외 메시지 생성기 (그대로 유지)
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
                        st.success("✅ 생성 완료! 상황에 맞게 복사해서 사용하세요.")
                    except Exception as e:
                        if "429" in str(e): st.error("🚨 구글 AI 서버 한도 초과입니다. 30초 뒤 다시 눌러주세요.")
                        else: st.error(f"오류 발생: {e}")
