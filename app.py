import streamlit as st
import pandas as pd
from google import genai
from apify_client import ApifyClient

st.set_page_config(page_title="AI 인플루언서 추출기", layout="wide")
st.title("✨ AI 인플루언서 추출기")
st.markdown("인스타그램 아이디, 이름, 계정 설명, 평균 좋아요 수 등을 한 번에 추출하고 AI로 검증하세요.")

GEMINI_KEY = "AQ.Ab8RN6LCth3UNX4taroMZ1hqh57YFmYwWfkfw2Yi-R93FVgwbg"
APIFY_TOKEN = "apify_api_bjEdwAY1D8iyURBVYsSxAqaCBBxfsL0X9CQ4"

with st.sidebar:
    st.header("🔍 검색 조건 세팅")
    search_hashtag = st.text_input("해시태그 (# 제외)", value="야구직관")
    max_posts = st.slider("추출할 계정 수", min_value=5, max_value=100, value=10, step=5)
    brand_target = st.text_area("AI 판별 기준", value="야구(KBO)를 진심으로 좋아하고, 경기장 직관 콘텐츠를 올리며 팬들과 소통하는 인플루언서")
    run_btn = st.button("🚀 데이터 추출 및 분석 시작", use_container_width=True)

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
                            "likes": [], 
                            "captions": []
                        }
                    # 좋아요 수집 (숨김 처리된 경우를 대비해 -1 등도 일단 수집)
                    user_data_map[username]["likes"].append(item.get("likesCount", -1))
                    
                    caption = item.get("caption", "")
                    if caption:
                        user_data_map[username]["captions"].append(caption)

                final_list = []
                progress_bar = st.progress(0)
                total_users = len(user_data_map)
                
                for idx, (username, info) in enumerate(user_data_map.items()):
                    # 💡 오류 1 해결: 숨김 처리된 좋아요(-1)를 제외하고 평균 계산
                    valid_likes = [l for l in info["likes"] if l != -1 and l is not None]
                    if valid_likes:
                        recent_likes = valid_likes[:9]
                        avg_likes = sum(recent_likes) / len(recent_likes)
                        avg_likes_str = f"{round(avg_likes, 1):,}개"
                    else:
                        avg_likes_str = "비공개 (숨김)"
                    
                    combined_caption = " / ".join(info["captions"])
                    if not combined_caption.strip():
                        combined_caption = "게시글 내용이 없거나 짧음"
                        
                    profile_link = f"https://instagram.com/{username}"
                    
                    # 💡 오류 2 해결: AI에게 실무자 페르소나 부여 및 출력 양식 강제 고정
                    prompt = f'''
                    너는 13년 차 온라인 마케팅 전문가이자, 사수 없는 마케터들을 이끄는 깐깐한 멘토야. 
                    아래 유저가 타겟({brand_target})에 부합하는 진짜 인플루언서인지 정밀하게 판별해.
                    
                    [유저 ID]: {username}
                    [게시글 내용]: {combined_caption}
                    
                    반드시 아래의 정확한 양식으로만 대답해. 다른 부연 설명은 절대 금지.
                    점수: [0~100 사이 숫자]
                    추천: [YES 또는 NO]
                    요약: [계정이 어떤 특징을 가졌는지 1~2줄로 요약된 핵심 설명]
                    '''
                    
                    score, recommend, bio_summary = "확인불가", "NO", "내용 부족으로 판별 불가"
                    try:
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        # 파싱 로직 강화 (줄 띄어쓰기 등 변수 차단)
                        for line in response.text.strip().split('\n'):
                            line = line.strip()
                            if line.startswith('점수:'): score = line.split(':', 1)[1].strip()
                            elif line.startswith('추천:'): recommend = line.split(':', 1)[1].strip()
                            elif line.startswith('요약:'): bio_summary = line.split(':', 1)[1].strip()
                    except:
                        pass
                    
                    final_list.append({
                        "인스타그램 아이디": username,
                        "이름": info["fullName"],
                        "계정 설명 (AI 요약)": bio_summary,
                        "최근 9개 평균 좋아요": avg_likes_str,
                        "AI 적합도 점수": score,
                        "링크": profile_link
                    })
                    progress_bar.progress((idx + 1) / total_users)

                df = pd.DataFrame(final_list)
                st.success("🎉 인플루언서 추출 및 분석 완료!")
                
                st.dataframe(
                    df,
                    column_config={"링크": st.column_config.LinkColumn("인스타그램 링크")},
                    hide_index=True,
                    use_container_width=True
                )
                
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                st.download_button(
                    label="📥 엑셀(CSV) 파일 다운로드",
                    data=csv,
                    file_name=f"인플루언서_추출기_{search_hashtag}.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"오류 발생: {e}")
