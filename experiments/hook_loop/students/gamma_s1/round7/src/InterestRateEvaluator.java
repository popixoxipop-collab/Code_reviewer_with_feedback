/**
 * 신용점수(1~1000)를 if/else if 조건 분기로 판정해 금리 등급(RateGrade)을 산정한다.
 *
 * <p>의존성 설계: LoanApplication 객체 전체가 아니라 int creditScore 하나만
 * evaluate()의 파라미터로 받는다. 이 클래스가 실제로 쓰는 값은 신용점수 하나뿐인데
 * LoanApplication을 통째로 넘기면, LoanApplication에 applicantName/loanAmount가
 * 추가·삭제·이름 변경될 때마다 이 클래스는 실제로는 영향이 없는데도 "관련 있어
 * 보이는" 클래스로 묶이게 된다. primitive 하나로 좁혀 받으면 그 불필요한 의존을
 * 원천적으로 끊을 수 있다 — 이는 RepaymentSchedule/InterestReport가 LoanApplication을
 * 통째로 받는 것과 의도적으로 다른 선택이다(그쪽은 필드 2개 이상을 실제로 사용해서
 * 객체 전달이 파라미터 목록 폭발을 막아주기 때문에 통째로 받는 편이 낫다).
 *
 * <p>fan_in=1 기록: 이 클래스는 현재 Main에서만 호출된다. 등급 산정 로직을
 * 인터페이스로 뽑아 여러 구현체를 갈아끼우는 구조로 만드는 것도 고려했지만,
 * 지금 시점엔 호출자가 하나뿐이라 과설계(YAGNI)라고 판단해 하지 않았다. 이후
 * "상품군별로 등급 산정 기준이 달라진다" 같은 요구가 실제로 생기면 그때
 * 인터페이스를 추출한다.
 *
 * <p>등급 구간은 국내 개인신용평점(NICE/KCB, 2021년 개편 이후) 1~1000점 스케일을
 * 참고해 100점 단위로 9등급으로 나눴다(1~300, 301~400, ... 951~1000). 각 구간의
 * 경계는 겹치지 않고 빈틈도 없다. LoanApplication 생성자가 이미 1~1000 범위를
 * 강제하므로 정상 흐름에서는 마지막 else 분기(300점 이하) 이상 값이 새어나갈 일이
 * 없어야 하지만, LoanApplication을 거치지 않고 evaluate()가 직접 호출되는 경로
 * (예: 단위 테스트, 향후 다른 입력 소스)에 대비해 else 분기까지 모든 정수 구간을
 * 빠짐없이 처리해 두었다.
 */
public class InterestRateEvaluator {

    public RateGrade evaluate(int creditScore) {
        String gradeLabel;
        double annualRatePercent;

        if (creditScore >= 951) {
            gradeLabel = "1등급";
            annualRatePercent = 3.5;
        } else if (creditScore >= 901) {
            gradeLabel = "2등급";
            annualRatePercent = 4.5;
        } else if (creditScore >= 801) {
            gradeLabel = "3등급";
            annualRatePercent = 5.5;
        } else if (creditScore >= 701) {
            gradeLabel = "4등급";
            annualRatePercent = 7.0;
        } else if (creditScore >= 601) {
            gradeLabel = "5등급";
            annualRatePercent = 9.0;
        } else if (creditScore >= 501) {
            gradeLabel = "6등급";
            annualRatePercent = 11.5;
        } else if (creditScore >= 401) {
            gradeLabel = "7등급";
            annualRatePercent = 14.0;
        } else if (creditScore >= 301) {
            gradeLabel = "8등급";
            annualRatePercent = 16.5;
        } else {
            // 방어적 분기(300점 이하): LoanApplication을 거쳐 들어오면 항상
            // 1~300 범위만 여기 도달한다. evaluate()가 LoanApplication 없이
            // 직접 호출되는 경우에도 최소한 예외 없이 가장 낮은 등급으로
            // 처리되도록 한다.
            gradeLabel = "9등급";
            annualRatePercent = 19.9;
        }

        return new RateGrade(gradeLabel, annualRatePercent);
    }
}
