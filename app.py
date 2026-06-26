import streamlit as st
import pandas as pd
import time
from google import genai
from apify_client import ApifyClient

st.set_page_config(page_title="AI 인플루언서 추출기 프로", layout="wide")
st.title("✨ AI 인플루언서 추출기 (SaaS 업그레이드 버전)")
st.markdown("더 넓은 데이터 수집 풀과 정교한 팔로워 필터링, 에러 없는 듀얼 섭외 문구 생성기까지 제공합니다.")

GEMINI_KEY = "AQ.Ab8RN6LCth3UNX4taroMZ1hqh57YFmYwWfkfw2Yi-R93FVgwbg"
APIFY_TOKEN = "apify_api_bjEdwAY1D8iyURBVYsSxAqaCBBxfsL0X9CQ4"

tab1, tab2 = st.tabs(["🚀 1단계: 조건별 인플루언서 발굴", "✉️ 2단계: 듀얼 섭외 메시지 생성"])

# ==========================================
# [탭 1] 확장형 인플루언서 자동 추출기 (방어력 MAX)
# ==========================================
with tab1:
    with st.sidebar:
        st.header("🔍 발굴 조건 세팅")
        search_hashtag = st.text_input("메인 해시태그 (# 제외)", value="야구직관")
        
        st.subheader("🎯 인플루언서 규모 필터링")
        follower_range = st.slider("팔로워 수 범위 (명)", min_value=100, max_value=500000, value=(500, 50000), step=100)
        following_range = st.slider("팔로잉 수 범위 (명)", min_value=10, max_value=10000, value=(50, 3000), step=50)
        max_posts = st.slider("스캔할 게시글 수 (모수 확장용)", min_value=20, max_value=300, value=60, step=20)
        
        brand_target = st.text_area("AI 판별 기준", value="야구(KBO)를 진심으로 좋아하고, 경기장 직관 콘텐츠를 올리며 팬들과 소통하는 인플루언서")
        run_btn = st.button("🚀 조건에 맞는 인플루언서 추출", use_container_width=True, type="primary")

    if run_btn:
        if not search_hashtag:
            st.error("해시태그를 입력해 주세요.")
        else:
            with st.spinner(f"#{search_hashtag} 및 파생 해시태그를 총동원하여 데이터를 긁어모으는 중입니다..."):
                try:
                    client = genai.Client(api_key=GEMINI_KEY)
                    apify_client = ApifyClient(APIFY_TOKEN)

                    # 💡 강제 모수 확장: 인스타 알고리즘을 뚫기 위해 검색어를 5개로 강제 복제
                    target_hashtags = [
                        search_hashtag, 
                        f"{search_hashtag}추천", 
                        f"{search_hashtag}그램", 
                        f"{search_hashtag}일상",
                        f"{search_hashtag}투어"
                    ]
                    
                    run = apify_client.actor("apify/instagram-hashtag-scraper").call(
                        run_input={"hashtags": target_hashtags, "resultsLimit": max_posts}
                    )
                    
                    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
                    if not dataset_id:
                        dataset_id = run.get("default_dataset_id") if isinstance(run, dict) else run.default_dataset_id

                    user_data_map = {}
                    for item in apify_client.dataset(dataset_id).iterate_items():
                        username = item.get("ownerUsername", "unknown")
                        if username == "unknown": continue
                            
                        followers = item.get("ownerFollowersCount", 0)
                        following = item.get("ownerFollowingCount", 500) # 기본값 세팅
                        
                        # 💡 팔로워/팔로잉 범위 1차 필터링
                        if not (follower_range[0] <= followers <= follower_range[1]): continue
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

                    final_list = []
                    
                    if not user_data_map:
                        st.warning("⚠️ 지정하신 팔로워 범위에 맞는 유저가 없습니다. 왼쪽 슬라이더 범위를 넓히고 다시 시도해 보세요!")
                    else:
                        progress_bar = st.progress(0)
                        total_users = len(user_data_map)
                        
                        for idx, (username, info) in enumerate(user_data_map.items()):
                            time.sleep(1.5) # 안전 딜레이
                            
                            valid_likes = [l for l in info["likes"] if l != -1 and l is not None]
                            avg_likes_str = f"{round(sum(valid_likes[:9]) / len(valid_likes[:9]), 1):,}개" if valid_likes else "비공개"
                            
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
                                # 💡 가장 원초적이고 안전한 텍스트 파싱 방식으로 복구
                                for line in response.text.strip().split('\n'):
                                    if '점수:' in line: score = line.split(':', 1)[1].strip()
                                    if '추천:' in line: recommend = line.split(':', 1)[1].strip()
                                    if '요약:' in line: bio_summary = line.split(':', 1)[1].strip()
                            except Exception as e:
                                if "429" in str(e): bio_summary = "⏳ 한도 초과 대기 중"
                                else: pass
                            
                            final_list.append({
                                "인스타그램 아이디": username, "이름": info["fullName"],
                                "팔로워 수": f"{info['followers']:,}명", "팔로잉 수": f"{info['following']:,}명",
                                "계정 설명 (AI 요약)": bio_summary, "최근 9개 평균 좋아요": avg_likes_str,
                                "AI 점수": score, "링크": profile_link
                            })
                            progress_bar.progress((idx + 1) / total_users)

                        df = pd.DataFrame(final_list)
                        st.success(f"🎉 필터링 통과 유저 {len(df)}명 분석 완료!")
                        st.dataframe(df, column_config={"링크": st.column_config.LinkColumn("인스타그램 링크")}, hide_index=True, use_container_width=True)
                        
                        csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                        st.download_button("📥 필터링 완료 명단 다운로드(CSV)", data=csv, file_name=f"추출결과_{search_hashtag}.csv", mime="text/csv")
                        
                except Exception as e:
                    st.error(f"오류 발생: {e}")

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
                        if "429" in str(e): st.error("🚨 구글 AI 서버 무료 한도 대기 중입니다. 30초 뒤 다시 눌러주세요.")
                        else: st.error(f"오류 발생: {e}")
