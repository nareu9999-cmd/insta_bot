import streamlit as st
import pandas as pd
from google import genai
from apify_client import ApifyClient

# 페이지 기본 설정
st.set_page_config(page_title="AI 인플루언서 추출기", layout="wide")
st.title("✨ AI 인플루언서 추출기")
st.markdown("인스타그램 아이디, 이름, 계정 설명, 평균 좋아요 수 등을 한 번에 추출하고 AI로 검증하세요.")

# API 세팅 (💡주의: 공유 시 타인이 무단으로 많이 사용하면 내 API 한도가 차감됩니다)
GEMINI_KEY = "AQ.Ab8RN6LCth3UNX4taroMZ1hqh57YFmYwWfkfw2Yi-R93FVgwbg"
APIFY_TOKEN = "apify_api_bjEdwAY1D8iyURBVYsSxAqaCBBxfsL0X9CQ4"

# 사이드바 입력창
with st.sidebar:
    st.header("🔍 검색 조건 세팅")
    search_hashtag = st.text_input("해시태그 (# 제외)", value="야구직관")
    max_posts = st.slider("추출할 계정 수", min_value=5, max_value=100, value=10, step=5)
    brand_target = st.text_area("AI 판별 기준", value="야구(KBO)를 진심으로 좋아하고, 경기장 직관 콘텐츠를 올리며 팬들과 소통하는 인플루언서")
    run_btn = st.button("🚀 데이터 추출 및 분석 시작", use_container_width=True)

# 메인 추출 및 분석 로직
if run_btn:
    if not search_hashtag:
        st.error("해시태그를 입력해 주세요.")
    else:
        with st.spinner(f"#{search_hashtag} 관련 계정을 추출하고 AI로 분석 중입니다..."):
            try:
                client = genai.Client(api_key=GEMINI_KEY)
                apify_client = ApifyClient(APIFY_TOKEN)

                run = apify_client.actor("apify/instagram-hashtag-scraper").call(
                    run_input={"hashtags": [search_hashtag], "resultsLimit": max_posts}
                )
                
                dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else getattr(run, "default_dataset_id", None)
                if not dataset_id:
                    dataset_id = run.get("default_dataset_id") if isinstance(run, dict) else run.default_dataset_id

                user_data_map = {}
                for item in apify_client.dataset(dataset_id).iterate_items():
                    username = item.get("ownerUsername", "알 수 없음")
                    if username not in user_data_map:
                        user_data_map[username] = {
                            "fullName": item.get("ownerFullName", "이름 없음"),
                            "followers": item.get("ownerFollowersCount", 0),
                            "likes": [], 
                            "captions": []
                        }
                    user_data_map[username]["likes"].append(item.get("likesCount", 0))
                    user_data_map[username]["captions"].append(item.get("caption", "내용 없음"))

                final_list = []
                progress_bar = st.progress(0)
                total_users = len(user_data_map)
                
                for idx, (username, info) in enumerate(user_data_map.items()):
                    # 최근 9개 평균 좋아요
                    recent_likes = info["likes"][:9]
                    avg_likes = sum(recent_likes) / len(recent_likes) if recent_likes else 0
                    
                    combined_caption = " / ".join(info["captions"])
                    profile_link = f"https://instagram.com/{username}"
                    
                    prompt = f'''
                    너는 마케팅 전문가야. 아래 유저가 타겟({brand_target})에 부합하는지 판별해 줘.
                    [유저 ID]: {username}
                    [게시글 내용]: {combined_caption}
                    결과는 반드시 아래 양식으로만 출력해.
                    점수: [숫자]
                    추천: [YES 또는 NO]
                    요약설명: [계정이 어떤 특징을 가졌는지 1~2줄로 요약된 계정 설명 작성]
                    '''
                    
                    score, recommend, bio_summary = "0", "NO", "정보 부족"
                    try:
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        for line in response.text.split('\n'):
                            if '점수' in line and ':' in line: score = line.split(':', 1)[1].strip()
                            elif '추천' in line and ':' in line: recommend = line.split(':', 1)[1].strip()
                            elif '요약설명' in line and ':' in line: bio_summary = line.split(':', 1)[1].strip()
                    except:
                        pass
                    
                    final_list.append({
                        "인스타그램 아이디": username,
                        "이름": info["fullName"],
                        "계정 설명 (AI 요약)": bio_summary,
                        "최근 9개 평균 좋아요": f"{round(avg_likes, 1):,}개",
                        "AI 적합도 점수": score,
                        "링크": profile_link
                    })
                    progress_bar.progress((idx + 1) / total_users)

                df = pd.DataFrame(final_list)
                st.success("🎉 인플루언서 추출 및 분석 완료!")
                
                # 표에 클릭 가능한 링크 적용 및 노출
                st.dataframe(
                    df,
                    column_config={
                        "링크": st.column_config.LinkColumn("인스타그램 링크")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # 엑셀 다운로드
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                st.download_button(
                    label="📥 엑셀(CSV) 파일 다운로드",
                    data=csv,
                    file_name=f"인플루언서_추출기_{search_hashtag}.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"오류 발생: {e}")
