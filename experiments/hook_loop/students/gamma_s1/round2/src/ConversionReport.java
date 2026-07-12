import java.util.List;

/**
 * ConversionHistory가 들고 있는 변환 기록들을 사람이 보기 좋은 형태로
 * 요약해서 출력하는 클래스.
 *
 * <p>현재 이 프로젝트에서 ConversionReport를 사용하는 곳은
 * ConversionHistory 한 곳뿐이라 fan-in은 1이다. "출력 방식을 바꾸고
 * 싶다"는 요구가 ConversionHistory와 무관하게 자주 생긴다면(예: 콘솔
 * 출력 대신 파일/JSON으로 내보내기), 그때는 출력 포맷 종류별로
 * ConversionReport를 인터페이스로 추출하는 것을 고려할 만하다. 지금은
 * fan-in이 낮고 요구사항도 "콘솔에 요약 출력" 하나뿐이라 그렇게까지
 * 분리할 실익은 없다.
 */
public class ConversionReport {

    /**
     * 변환 기록 목록을 요약해서 System.out에 출력한다.
     * 총 변환 횟수, 마지막 변환 결과, 평균 변환 결과, 전체 이력을 포함한다.
     *
     * @param records 출력할 변환 기록 목록 (비어 있어도 됨)
     */
    public void print(List<ConversionRecord> records) {
        System.out.println();
        System.out.println("===== 변환 이력 요약 =====");
        System.out.println("총 변환 횟수 : " + records.size() + "회");

        if (records.isEmpty()) {
            System.out.println("(이번 실행에서 수행한 변환이 없습니다)");
            System.out.println("==========================");
            return;
        }

        ConversionRecord last = records.get(records.size() - 1);
        System.out.println("마지막 변환   : " + last);
        System.out.printf("평균 변환 결과 : %.2f%n", averageConvertedValue(records));

        System.out.println("--- 전체 이력 ---");
        for (int i = 0; i < records.size(); i++) {
            System.out.printf("%3d. %s%n", i + 1, records.get(i));
        }
        System.out.println("==========================");
    }

    /**
     * 변환 결과 값들의 평균을 계산한다.
     *
     * <p>누적합(sum)과 반환 타입을 int가 아닌 double로 쓰는 이유:
     * 변환 결과 자체가 이미 소수 값(double)이므로 합계를 int로 누적하면
     * 소수부가 잘려나가 평균이 부정확해진다(정확도 제약). 반면 나눗셈에
     * 쓰이는 개수(count)는 records.size()가 반환하는 int를 그대로
     * 사용하는데, double 나눗셈에 int가 섞이면 자동으로 double 승격
     * (promotion)이 일어나므로 정확도 손실은 없다. 오버플로우 관점에서도
     * sum이 double이라 실질적으로 문제될 범위가 아니다 — 이 프로그램이
     * 다루는 온도 값과 한 실행에서 발생 가능한 레코드 수 모두 double의
     * 표현 범위에 비하면 무시할 수준이기 때문이다.
     *
     * @param records 평균을 계산할 변환 기록 목록 (비어 있지 않아야 함)
     * @return 변환 결과 값들의 평균
     */
    private double averageConvertedValue(List<ConversionRecord> records) {
        double sum = 0.0;
        for (ConversionRecord record : records) {
            sum += record.getConvertedValue();
        }
        return sum / records.size();
    }
}
