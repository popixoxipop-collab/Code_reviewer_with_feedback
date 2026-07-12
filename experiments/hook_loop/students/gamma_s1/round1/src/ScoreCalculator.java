import java.util.List;

/**
 * 학생 점수의 평균/최고점을 계산하는 클래스.
 */
public class ScoreCalculator {

    public double calculateAverage(List<Student> students) {
        if (students == null || students.isEmpty()) {
            return 0.0;
        }

        int total = 0;
        for (Student student : students) {
            total += student.getScore();
        }

        return (double) total / students.size();
    }

    public int calculateMax(List<Student> students) {
        if (students == null || students.isEmpty()) {
            return 0;
        }

        int max = students.get(0).getScore();
        for (Student student : students) {
            if (student.getScore() > max) {
                max = student.getScore();
            }
        }

        return max;
    }
}
