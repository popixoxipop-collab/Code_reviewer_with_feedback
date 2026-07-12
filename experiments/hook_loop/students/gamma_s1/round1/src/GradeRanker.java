import java.util.List;

/**
 * 학생별 등급(A/B/C)을 판정하는 클래스.
 * ScoreCalculator가 계산한 최고점을 활용해, 최고점자는 항상 A를 받도록 한다.
 */
public class GradeRanker {
    private ScoreCalculator scoreCalculator;

    public GradeRanker(ScoreCalculator scoreCalculator) {
        this.scoreCalculator = scoreCalculator;
    }

    /**
     * 90점 이상이거나 전체 중 최고점인 경우 A, 70점 이상이면 B, 그 외는 C.
     */
    public String determineGrade(Student student, List<Student> allStudents) {
        int score = student.getScore();
        int maxScore = scoreCalculator.calculateMax(allStudents);

        if (score >= 90 || score == maxScore) {
            return "A";
        } else if (score >= 70) {
            return "B";
        } else {
            return "C";
        }
    }
}
