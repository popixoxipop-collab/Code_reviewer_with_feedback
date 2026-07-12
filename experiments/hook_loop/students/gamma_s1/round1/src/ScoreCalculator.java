/**
 * 학생 점수들의 평균과 최고점을 계산하는 클래스.
 */
public class ScoreCalculator {

    /**
     * 학생 배열의 평균 점수를 계산한다.
     */
    public double calculateAverage(Student[] students) {
        double sum = 0;
        for (Student s : students) {
            sum += s.getScore();
        }
        return sum / students.length;
    }

    /**
     * 학생 배열 중 최고 점수를 계산한다.
     */
    public double calculateMax(Student[] students) {
        double max = students[0].getScore();
        for (Student s : students) {
            if (s.getScore() > max) {
                max = s.getScore();
            }
        }
        return max;
    }

    /**
     * 최고 점수를 받은 학생을 찾는다.
     */
    public Student findTopStudent(Student[] students) {
        Student top = students[0];
        for (Student s : students) {
            if (s.getScore() > top.getScore()) {
                top = s;
            }
        }
        return top;
    }
}
